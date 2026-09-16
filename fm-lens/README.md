# fm-lens

**FM Lens** is agentic FileMaker development for machines that have Claris's
**Agentic Development Toolkit (ADT)** installed. It was called `fm-adt-helper`
up to 0.1.4.

It has two parts:

- **The FM Lens FileMaker plug-in** (`plugin/`): an agent's eyes and hands
  inside FileMaker Pro.
- **Skills** that fill what Claris's own `filemaker-agentic-development`
  plugin leaves out.

Which gaps it fills is re-checked on every ADT build
(`fm-ADT-testing/docs/helper-gap-ledger.md`). Anything Claris starts covering
gets removed here.

## Install alongside Claris's plugin, INSTEAD of fm-dc

One machine, one DataCraft FileMaker plugin:

- **ADT installed** (`fm` on PATH, Claris `filemaker-agentic-development` in
  Claude Code) → install **fm-lens**.
- **No ADT** → install **fm-dc** and use its pipeline.

## Skills

| Skill | Covers |
|---|---|
| `fm-lens` | The FM Lens plug-in: snapshots (window, one layout object, web viewer), state, menus, go-to-layout, modes, new record, dialog handling, open and close, script starting, XML clipboard, and the file and app command channels |
| `adt-workflow` | The top-level map: what ADT is, the two-lane architecture, lane selection, and the in-FileMaker routing rule (FM Lens vs MBS/BaseElements, never a mix) |
| `adt-native-layouts` | Native layout authoring and its render traps: the theme rule (quirk 106), field-height minimums, parts and themes from 0.7.0 |
| `adt-capabilities` | Generated per ADT build: what works, the verified cookbook, and the don't-attempt list |
| `adt-quirks` | The master quirks list. Consult whenever ADT behaves surprisingly |
| `fm-cli-notes` | Supplements Claris's `fm-cli`: headless ExecuteSQL reads, calc and step shape traps, dbError triage |
| `adt-cli` | The `adt` project CLI and adt.json anatomy |
| `adt-connections` | The connection lifecycle, extended-privilege gotchas, and the force-refresh unwedge |
| `adt-webviewer` | HTML apps inside the file: app add, layout add, build, deploy |

## The FM Lens plug-in

`plugin/` ships FM Lens 0.5.0: a prebuilt arm64 bundle plus its source, built
from the Claris Plug-In SDK. It captures windows, single objects and web
viewers to PNG in-process, with no Screen Recording permission. Its two
drop-folder channels drive FileMaker's menus, dialogs and scripts. The app
channel keeps answering while a modal dialog has stalled FileMaker.

Install with `make install-prebuilt` in `plugin/`. The `fm-lens` skill
documents everything else.

## Requirements

- Claris ADT 0.7.0+ (`fm` on PATH; the `filemaker-agentic-development` Claude
  Code plugin).
- The **`agenticdev` standards pack** (`agenticdev-filemaker-standards`),
  declared in each project's `adt.json`. The `adt-workflow` skill explains why.
- FileMaker Pro 2025 (26.x). Hosted files need FileMaker Server ≥ 26.
- Node + pnpm, only for web viewer app work.
