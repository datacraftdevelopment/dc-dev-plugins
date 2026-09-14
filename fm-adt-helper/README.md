# fm-adt-helper

Agentic FileMaker development for machines that have Claris's **Agentic
Development Toolkit (ADT)** installed. This plugin is the ADT-era sibling of
`fm-dc`: it carries the workflow doctrine distilled from a hands-on exploration
of ADT 0.4.0 (build 29793558) — a blank file built into a working CRM entirely
through ADT's own surfaces, with every quirk found along the way written down.

## Install this INSTEAD of fm-dc

One machine, one FileMaker plugin — never both:

- **ADT CLIs installed** (`fm` on PATH, Claris `filemaker-agentic-development`
  plugin in Claude Code) → install **fm-adt-helper**. ADT's own `fm`/`adt`
  CLIs and MCP tools replace fm-dc's SaXML patch pipeline, OData/Data API
  tool-skills, and connection router.
- **No ADT** → install **fm-dc** and work through its pipeline as before.

The skills here assume ADT's surfaces exist and route everything through them.

## Skills

| Skill | Covers |
|---|---|
| `adt-workflow` | The top-level map: what ADT is, the two-lane architecture, lane selection, and the in-FileMaker capability routing rule (ADT Helper vs MBS/BaseElements — never a mix) |
| `fm-cli` | The `fm` schema engine: NDJSON op grammar, dry-run → apply → fresh verify, self-documenting help tree, credentials, and headless data reads via evaluate:calculation + ExecuteSQL |
| `adt-cli` | The `adt` project CLI: init, connect, components, app add, layout add, typegen, deploy, doctor — and adt.json anatomy |
| `adt-connections` | The connection lifecycle: sharing → record → provision → handshake, extended-privilege gotchas, and the force-refresh unwedge |
| `adt-webviewer` | HTML apps inside the file: app add → layout add → build → deploy, typed clients, and the pnpm trust-policy gotcha |
| `adt-native-layouts` | Native layout authoring: what fm can place, the two-pass pattern, Apex Blue field-height minimums, and the passes-validation-but-renders-broken trap |
| `adt-quirks` | The master quirks list — consult whenever ADT behaves surprisingly |
| `adt-helper` | The ADT Helper FileMaker plug-in: snapshots (window + web viewer), state probes, script starting, XML clipboard, and the drop-folder command channel |

## The ADT Helper FileMaker plug-in

The `plugin/` folder ships the **ADT Helper** FileMaker plug-in v0.3.0
(prebuilt arm64 bundle + source, built from the Claris Plug-In SDK). It closes
ADT's visual-verification gap and more: window + web viewer snapshots rendered
in-process to PNG (no Screen Recording permission), state probes, script
starting without fmp URLs, FileMaker XML clipboard get/set, and a drop-folder
command channel driven from the plug-in idle loop. Install with
`make install-prebuilt` in `plugin/`; the `adt-helper` skill documents the
function surface and channel protocol.

## Requirements

- Claris ADT 0.4.0+ installed (`fm` at `~/.local/bin/fm`; the
  `filemaker-agentic-development` Claude Code plugin)
- FileMaker Pro 2025 (26.x); hosted files need FileMaker Server ≥ 26
- Node + pnpm only for web viewer app work
