---
name: fm-xml
description: >
  FileMaker XML in every form — generating paste-ready fmxmlsnippet XML for scripts,
  custom functions, layout objects, and field definitions; reviewing snippet XML for
  silent paste-handler failures; and reading Save-as-XML / DDR export grammar.
  Use whenever the user wants FileMaker XML generated from a description or pseudocode,
  pastes fmxmlsnippet XML to modify, mentions LayoutObjectList or FMObjectList, asks about
  script step XML shapes, field definitions for Manage Database, or needs to understand
  a Save a Copy as XML export's structure. Do not attempt FileMaker XML from memory alone —
  always load the matching guide below first.
---

# FileMaker XML

One skill owns "producing or reading FileMaker XML." Route by task, load only the guide you need (each is self-contained with worked examples):

| Task | Load |
|---|---|
| Script XML or custom-function XML (generate, modify, review) | [references/snippets/GUIDE.md](references/snippets/GUIDE.md) — 220+ step IDs, element ordering, silent-failure rules, FM 2026 steps |
| Layout object XML (fields, portals, tab controls, popovers, button bars, web viewers — all 18 object types) | [references/layout/GUIDE.md](references/layout/GUIDE.md) — always run its theme pre-flight before generating |
| Field definition XML for Manage Database (auto-enter, validation, calc/summary fields) | [references/field/GUIDE.md](references/field/GUIDE.md) — note: pasting field defs requires the MBS plugin |
| Understanding a Save-as-XML / DDR export's structure (catalogs, references, step text) | [references/ddr_xml_structure.md](references/ddr_xml_structure.md) |
| Ground truth for any XML shape question | [references/ooe-source.md](references/ooe-source.md) — Mislav Kos's One-of-Everything file, the canonical corpus |

## Non-negotiable rules

1. **Validate every snippet before it goes anywhere near FileMaker:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/tools/fmlint/validate_snippet.py <file-or-dir>
   ```
   Catches unbalanced blocks, unknown step names, unclosed calculations, naming/documentation issues. No exceptions — a snippet that fails lint does not get pasted or patched.
2. **Never invent XML shape from memory.** The shape comes from the guides and the OOE corpus; the model's job is slotting values into known shapes. If a shape isn't covered, say so and check a real export rather than guessing.
3. **Delivery is a separate decision.** Generating XML is this skill; getting it into a file is either the clipboard (human paste — scripts into Script Workspace, layout objects in Layout mode) or the patch pipeline (fm-patch skill / fm-patch-builder agent). Consult fm-patch's tier rules before choosing.
4. **Round-trip edits of an existing database's scripts** (paste in → modify with schema awareness → paste back) are the fm-scripts skill's job — it layers this skill's formats over the project's `schema/readable/` knowledge base.
