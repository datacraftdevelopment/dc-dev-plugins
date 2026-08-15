#!/usr/bin/env node
/**
 * excalidraw-readback — pull annotations out of a marked-up .excalidraw scene
 * and report what each one sits on top of.
 *
 *   node excalidraw-readback.mjs --scene marked.excalidraw --map doc.map.json [--json]
 *
 * The .map.json sidecar was written by html-to-excalidraw.mjs at creation time
 * and freezes the document's text-block geometry — so this script is pure JSON
 * math: no Chrome, no re-render, immune to the HTML having been edited since.
 *
 * The scene identifies itself: the locked backdrop's element id is recorded in
 * the sidecar, and both survive excalidraw.com's load→save byte-identical.
 * If they don't match, you're reading the wrong map — the script says so.
 *
 * Anything locked is backdrop; everything else is an annotation.
 */

import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(`--${n}`); return i !== -1 && argv[i + 1] ? argv[i + 1] : d; };
const has = (n) => argv.includes(`--${n}`);

const scenePath = arg('scene');
const mapArg = arg('map');
if (!scenePath || !mapArg) {
  console.error('usage: node excalidraw-readback.mjs --scene <marked.excalidraw> --map <doc.map.json> [--json]');
  process.exit(1);
}

// ── geometry ──────────────────────────────────────────────────────────────────

/** absolute bounding box of any annotation element */
const bbox = (el) => {
  if ((el.type === 'freedraw' || el.type === 'line' || el.type === 'arrow')
      && Array.isArray(el.points) && el.points.length) {
    const xs = el.points.map((p) => p[0]), ys = el.points.map((p) => p[1]);
    return {
      x1: el.x + Math.min(...xs), y1: el.y + Math.min(...ys),
      x2: el.x + Math.max(...xs), y2: el.y + Math.max(...ys),
    };
  }
  return { x1: el.x, y1: el.y, x2: el.x + (el.width || 0), y2: el.y + (el.height || 0) };
};

const overlap = (a, blk) => {
  const ox = Math.max(0, Math.min(a.x2, blk.x + blk.w) - Math.max(a.x1, blk.x));
  const oy = Math.max(0, Math.min(a.y2, blk.y + blk.h) - Math.max(a.y1, blk.y));
  return ox * oy;
};

// arrows point somewhere; where the head lands matters more than the shaft's box
const arrowTip = (el) => {
  if (el.type !== 'arrow' || !Array.isArray(el.points) || !el.points.length) return null;
  const p = el.points[el.points.length - 1];
  return { x: el.x + p[0], y: el.y + p[1] };
};

async function main() {
  const scene = JSON.parse(await readFile(resolve(scenePath), 'utf8'));
  const map = JSON.parse(await readFile(resolve(mapArg), 'utf8'));

  if (map.format !== 'excalidraw-artifact-map/1') {
    console.error(`warning: unrecognized map format "${map.format}"`);
  }

  const backdrop = scene.elements.find((e) => e.type === 'image' && e.locked && !e.isDeleted);
  if (!backdrop) {
    console.error('error: no locked backdrop image in the scene — is this a converted artifact?');
    process.exit(1);
  }
  if (backdrop.id !== map.backdropElementId) {
    console.error(`error: scene backdrop id "${backdrop.id}" ≠ map's "${map.backdropElementId}" — this map belongs to a different document.`);
    process.exit(1);
  }

  // scene coords → document coords (identity when the backdrop wasn't moved/resized)
  const sx = backdrop.width / map.width;
  const toDoc = (b) => ({
    x1: (b.x1 - backdrop.x) / sx, y1: (b.y1 - backdrop.y) / sx,
    x2: (b.x2 - backdrop.x) / sx, y2: (b.y2 - backdrop.y) / sx,
  });

  const marks = scene.elements.filter((e) => !e.isDeleted && !(e.type === 'image' && e.locked));
  const blocks = map.blocks;

  const findings = marks.map((el) => {
    const doc = toDoc(bbox(el));

    let hits = blocks
      .map((blk) => ({ blk, area: overlap(doc, blk) }))
      .filter((h) => h.area > 0)
      .sort((a, b) => b.area - a.area);

    // an arrow's meaning concentrates at its tip — prefer the block under it
    const tip = arrowTip(el);
    if (tip) {
      const tdoc = { x: (tip.x - backdrop.x) / sx, y: (tip.y - backdrop.y) / sx };
      const under = blocks.filter((b) =>
        tdoc.x >= b.x && tdoc.x <= b.x + b.w && tdoc.y >= b.y && tdoc.y <= b.y + b.h);
      if (under.length) hits = under.map((blk) => ({ blk, area: blk.w * blk.h })).concat(
        hits.filter((h) => !under.includes(h.blk)));
    }

    // margin marks cover nothing; report the vertically nearest block instead
    let nearest = null;
    if (!hits.length) {
      const mid = (doc.y1 + doc.y2) / 2;
      nearest = blocks
        .map((blk) => ({ blk, d: Math.abs(blk.y + blk.h / 2 - mid) }))
        .sort((a, b) => a.d - b.d)[0];
    }

    return {
      type: el.type,
      color: el.strokeColor,
      text: el.text ?? null,
      doc: {
        x: Math.round(doc.x1), y: Math.round(doc.y1),
        w: Math.round(doc.x2 - doc.x1), h: Math.round(doc.y2 - doc.y1),
      },
      covers: hits.slice(0, 4).map((h) => ({
        tag: h.blk.tag, section: h.blk.section, text: h.blk.text,
      })),
      nearest: nearest ? {
        tag: nearest.blk.tag, section: nearest.blk.section,
        text: nearest.blk.text, distance: Math.round(nearest.d),
      } : null,
    };
  });

  // reading order: top of the document first
  findings.sort((a, b) => a.doc.y - b.doc.y);

  if (has('json')) {
    console.log(JSON.stringify({ source: map.sourceHtml, findings }, null, 2));
    return;
  }

  console.log(`source: ${map.sourceHtml}`);
  console.log(`${findings.length} annotation(s), in reading order\n`);
  findings.forEach((f, i) => {
    console.log(`── ${i + 1}. ${f.type}${f.color ? ` (${f.color})` : ''} at y=${f.doc.y}, ${f.doc.w}×${f.doc.h}`);
    if (f.text) console.log(`   note: "${f.text}"`);
    if (f.covers.length) {
      console.log('   sits on:');
      f.covers.forEach((c) =>
        console.log(`     · [${c.tag}]${c.section ? ` (${c.section})` : ''} ${c.text.slice(0, 150)}`));
    } else if (f.nearest) {
      console.log(`   covers nothing; nearest block (${f.nearest.distance}px away):`);
      console.log(`     · [${f.nearest.tag}]${f.nearest.section ? ` (${f.nearest.section})` : ''} ${f.nearest.text.slice(0, 150)}`);
    }
    console.log();
  });
}

main().catch((e) => { console.error(e); process.exit(1); });
