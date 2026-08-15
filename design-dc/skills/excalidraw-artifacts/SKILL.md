---
name: excalidraw-artifacts
description: Convert an HTML artifact into a markup-ready Excalidraw canvas, and read the annotations back out afterwards. Use when Joe wants to mark up a document in Excalidraw — "make this an Excalidraw", "I want to draw on this for my talk", "excalidraw version of this" — and for the return trip, when he brings back a marked-up .excalidraw file and wants the circles, arrows, and notes read and correlated with what they sit on. Pairs with html-artifacts (which produces the source document); this skill handles the canvas round trip.
---

# Excalidraw Artifacts

Joe gives talks and marks up documents live in Excalidraw — circling things,
drawing arrows, dropping notes. This skill covers both directions of that loop:

1. **Create** — render an HTML document to a single full-page PNG, embedded as a
   **locked** background image in a `.excalidraw` scene. Joe draws on top; the
   backdrop can't be nudged or selected.
2. **Read back** — take the marked-up file after the talk and report every
   annotation with the document content it sits on.

Both scripts live in `scripts/` beside this file. Zero npm dependencies — they
drive the installed Google Chrome over the DevTools Protocol.

## Creating a canvas

If the document doesn't exist yet, produce it first with the `html-artifacts`
skill — that owns the editorial style. Then:

```bash
node "<this skill>/scripts/html-to-excalidraw.mjs" --html doc.html [--out doc.excalidraw] [--width 900] [--scale 2]
```

Output is **two files** — always keep them together:

- `doc.excalidraw` — the scene. Open at excalidraw.com (File → Open or drag in).
- `doc.map.json` — sidecar freezing every text block's geometry at creation
  time. This is what makes the return trip cheap and reliable; without it,
  readback needs Chrome and breaks if the HTML was edited since.

Defaults (900px wide, 2× retina) are right for talk documents; don't ask.
A ~7000px-tall document lands around 3 MB — fine.

**One tall image, never sliced panels.** A multi-panel variant was tried and
failed to open for Joe (2026-08-15); the single locked image is the verified
form. Don't convert the document to native Excalidraw shapes either — markup on
top is the whole point.

## Reading annotations back

When Joe returns with a marked-up file (often from `~/Downloads`, often named
`Untitled-<date>.excalidraw`):

```bash
node "<this skill>/scripts/excalidraw-readback.mjs" --scene marked.excalidraw --map doc.map.json [--json]
```

- Pure JSON math — no Chrome, runs in milliseconds.
- Locked image = backdrop; everything else = annotation.
- Each annotation reports the text blocks it covers (by overlap area, largest
  first), tagged with its section heading. Arrows resolve by where the **tip**
  lands. Margin marks that cover nothing report the nearest block instead.
- The scene self-identifies: the backdrop's element id must match the map's.
  On mismatch the script exits 1 and names the problem — find the right
  `.map.json` (it lives next to the original `.excalidraw`), don't override.

When relaying results to Joe, interpret — don't dump. A circle is a strong
signal about exactly what it encloses; a floating text note is positional
evidence only (he may mean the card, the section, or the whole document —
say which reading you chose). Present findings in reading order.

## Why this design (don't "improve" these away)

- **Backdrop at (0,0), scale 1, locked** → scene coordinates ARE document
  coordinates. The identity transform is the feature.
- **Deterministic ids** (`bgimg-<hash>` / `bg-<hash>`) → verified to survive
  excalidraw.com's load→save byte-identical (0.18.1). The returned file tells
  you which document it came from.
- **Sidecar, not `customData`** → Excalidraw's restore path silently drops
  `customData`; embedding the map in the scene does not survive. The sidecar
  keyed by element id does.
- **`Page.captureScreenshot` with `captureBeyondViewport`** → Chrome's plain
  `--screenshot` CLI flag clips to the viewport and cannot capture a full page.

## Gotchas

- If Chrome isn't at the default macOS path, set `CHROME_PATH`.
- Readback treats **every** unlocked element as an annotation. If Joe unlocked
  and moved the backdrop mid-talk, the coordinate transform still corrects for
  translation and uniform resize — but a deleted backdrop means no anchor.
- The map matches the HTML **as rendered at creation**. If the document is
  re-rendered after edits, regenerate the canvas; don't reuse the old map.
