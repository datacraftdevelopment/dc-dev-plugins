#!/usr/bin/env node
/**
 * html-to-excalidraw — render an HTML document into a markup-ready .excalidraw
 * scene: one full-page PNG embedded as a locked background image, plus a
 * .map.json sidecar that lets annotations be read back later without Chrome.
 *
 * Zero dependencies. Drives the installed Google Chrome over the DevTools
 * Protocol (Node 22+ global WebSocket): Page.captureScreenshot with
 * captureBeyondViewport captures past the viewport and returns base64 PNG —
 * exactly the shape Excalidraw's embedded `files` dict wants. (Chrome's plain
 * --screenshot CLI flag can NOT do this; it clips to the viewport.)
 *
 *   node html-to-excalidraw.mjs --html doc.html [--out doc.excalidraw] [--width 900] [--scale 2]
 *
 * Round-trip design (all three matter):
 *   · backdrop locked:true at (0,0), scale 1  → scene coords ARE document coords
 *   · deterministic element id + fileId        → survive excalidraw.com load/save
 *     byte-identical (verified 0.18.1), so a returned file self-identifies
 *   · <out>.map.json sidecar                   → text-block geometry frozen at
 *     creation; readback is pure JSON math, immune to later HTML edits
 *   · do NOT use customData — silently dropped by the app's restore path
 */

import { spawn } from 'node:child_process';
import { writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, basename, extname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(`--${n}`); return i !== -1 && argv[i + 1] ? argv[i + 1] : d; };

const htmlPath = arg('html');
if (!htmlPath) {
  console.error('usage: node html-to-excalidraw.mjs --html <file.html> [--out <file.excalidraw>] [--width 900] [--scale 2]');
  process.exit(1);
}
const htmlAbs = resolve(htmlPath);
const outPath = resolve(arg('out', htmlAbs.replace(new RegExp(`${extname(htmlAbs)}$`), '.excalidraw')));
const mapPath = outPath.replace(/\.excalidraw$/, '.map.json');
const WIDTH = Number(arg('width', 900));
const SCALE = Number(arg('scale', 2));

const CHROME = process.env.CHROME_PATH
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── minimal CDP client ────────────────────────────────────────────────────────

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.listeners = [];
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id !== undefined && this.pending.has(msg.id)) {
        const { resolve: ok, reject: no } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? no(new Error(msg.error.message)) : ok(msg.result);
      } else if (msg.method) this.listeners.forEach((f) => f(msg));
    });
  }
  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((ok, no) => {
      ws.addEventListener('open', ok, { once: true });
      ws.addEventListener('error', () => no(new Error(`cannot connect to ${url}`)), { once: true });
    });
    return new CDP(ws);
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    return new Promise((ok, no) => {
      this.pending.set(id, { resolve: ok, reject: no });
      this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }
  once(method, sessionId) {
    return new Promise((ok) => {
      const fn = (m) => {
        if (m.method === method && (!sessionId || m.sessionId === sessionId)) {
          this.listeners = this.listeners.filter((f) => f !== fn); ok(m.params);
        }
      };
      this.listeners.push(fn);
    });
  }
  close() { this.ws.close(); }
}

// ── render + block extraction (one Chrome session for both) ──────────────────

async function renderAndMap(url) {
  const userDataDir = await mkdtemp(join(tmpdir(), 'h2e-'));
  const chrome = spawn(CHROME, [
    '--headless', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--force-color-profile=srgb',
    '--remote-debugging-port=0', `--user-data-dir=${userDataDir}`, 'about:blank',
  ], { stdio: ['ignore', 'pipe', 'pipe'] });

  const endpoint = await new Promise((res, rej) => {
    let buf = '';
    const t = setTimeout(() => rej(new Error('timed out waiting for Chrome DevTools endpoint')), 30000);
    chrome.stderr.on('data', (d) => {
      buf += d.toString();
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) { clearTimeout(t); res(m[1]); }
    });
    chrome.on('exit', (c) => { clearTimeout(t); rej(new Error(`Chrome exited early (code ${c})`)); });
  });

  const cdp = await CDP.connect(endpoint);
  try {
    const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
    await cdp.send('Page.enable', {}, sessionId);
    await cdp.send('Emulation.setDeviceMetricsOverride',
      { width: WIDTH, height: 1200, deviceScaleFactor: 1, mobile: false }, sessionId);

    const loaded = cdp.once('Page.loadEventFired', sessionId);
    await cdp.send('Page.navigate', { url }, sessionId);
    await loaded;
    await cdp.send('Runtime.evaluate',
      { expression: 'document.fonts ? document.fonts.ready.then(()=>true) : true', awaitPromise: true }, sessionId);
    await sleep(350);

    const { cssContentSize } = await cdp.send('Page.getLayoutMetrics', {}, sessionId);
    const cssHeight = Math.ceil(cssContentSize.height);
    await cdp.send('Emulation.setDeviceMetricsOverride',
      { width: WIDTH, height: cssHeight, deviceScaleFactor: 1, mobile: false }, sessionId);
    await sleep(200);

    // -- text-block geometry: leaf-ish blocks only, each tagged with its section
    const expression = `(() => {
      const SKIP = new Set(['SCRIPT','STYLE','HEAD','META','TITLE','LINK','BR']);
      const out = [];
      const walk = (node) => {
        for (const el of node.children) {
          if (SKIP.has(el.tagName)) continue;
          const text = (el.innerText || '').trim();
          if (!text) { walk(el); continue; }
          const hasBlockChild = Array.from(el.children).some((c) => {
            if (SKIP.has(c.tagName)) return false;
            const cs = getComputedStyle(c);
            return (cs.display !== 'inline' && (c.innerText || '').trim().length > 0);
          });
          if (hasBlockChild) { walk(el); continue; }
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          out.push({
            tag: el.tagName.toLowerCase(),
            x: Math.round(r.x + scrollX), y: Math.round(r.y + scrollY),
            w: Math.round(r.width), h: Math.round(r.height),
            text: text.replace(/\\s+/g, ' ').slice(0, 400),
          });
        }
      };
      walk(document.body);
      const heads = out.filter(b => ['h1','h2','h3'].includes(b.tag)).sort((a,b)=>a.y-b.y);
      out.forEach(b => {
        const h = [...heads].reverse().find(h => h.y <= b.y);
        b.section = h ? h.text.slice(0, 90) : null;
      });
      return JSON.stringify(out.sort((a,b)=>a.y-b.y));
    })()`;
    const { result } = await cdp.send('Runtime.evaluate', { expression, returnByValue: true }, sessionId);
    const blocks = JSON.parse(result.value);

    const { data } = await cdp.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: WIDTH, height: cssHeight, scale: SCALE },
    }, sessionId);

    return { base64: data, cssHeight, blocks };
  } finally {
    cdp.close(); chrome.kill();
    await rm(userDataDir, { recursive: true, force: true }).catch(() => {});
  }
}

// ── excalidraw scene ──────────────────────────────────────────────────────────

async function main() {
  const url = pathToFileURL(htmlAbs).href;
  process.stderr.write(`rendering ${basename(htmlAbs)} at ${WIDTH}px × ${SCALE}x …\n`);

  const { base64, cssHeight, blocks } = await renderAndMap(url);
  process.stderr.write(`captured ${WIDTH}×${cssHeight} css · ${blocks.length} text blocks mapped\n`);

  // deterministic ids from content — stable across re-runs of the same doc,
  // distinct across docs; verified to survive excalidraw.com load→save intact
  const digest = createHash('sha256').update(base64).digest('base64url').slice(0, 14);
  const fileId = `bg-${digest}`;
  const elementId = `bgimg-${digest}`;
  const created = 1755000000000;

  const scene = {
    type: 'excalidraw',
    version: 2,
    source: 'html-to-excalidraw',
    elements: [{
      id: elementId, type: 'image', x: 0, y: 0, width: WIDTH, height: cssHeight,
      angle: 0,
      strokeColor: 'transparent', backgroundColor: 'transparent',
      fillStyle: 'solid', strokeWidth: 1, strokeStyle: 'solid',
      roughness: 0, opacity: 100,
      groupIds: [], frameId: null, index: null, roundness: null,
      seed: 1, version: 1, versionNonce: 1,
      isDeleted: false, boundElements: null, updated: 1, link: null,
      locked: true,        // ← markup can never nudge or select the backdrop
      status: 'saved', fileId, scale: [1, 1], crop: null,
    }],
    appState: {
      gridSize: null, gridStep: 5, gridModeEnabled: false,
      viewBackgroundColor: '#F4ECE0',
    },
    files: {
      [fileId]: {
        mimeType: 'image/png', id: fileId,
        dataURL: `data:image/png;base64,${base64}`,
        created, lastRetrieved: created,
      },
    },
  };

  const map = {
    format: 'excalidraw-artifact-map/1',
    backdropElementId: elementId,
    backdropFileId: fileId,
    sourceHtml: htmlAbs,
    width: WIDTH,
    scale: SCALE,
    cssHeight,
    blocks,
  };

  await writeFile(outPath, JSON.stringify(scene));
  await writeFile(mapPath, JSON.stringify(map, null, 1));
  const mb = (JSON.stringify(scene).length / 1024 / 1024).toFixed(2);
  process.stderr.write(`wrote ${outPath} (${mb} MB)\n`);
  process.stderr.write(`wrote ${mapPath} (sidecar — keep it next to the scene for readback)\n`);
}

main().catch((e) => { console.error(e); process.exit(1); });
