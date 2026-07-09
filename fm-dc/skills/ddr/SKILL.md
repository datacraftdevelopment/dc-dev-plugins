---
name: ddr
description: Parse a FileMaker DDR / "Save a Copy as XML" export into analyzable per-object files AND an agent-readable knowledge base, so an agent can audit a FileMaker system and read/write its scripts and calcs as XML. Use when the user wants to parse, search, compare, or audit FileMaker database structure from a schema export (classic DDR or FM 2026 split-catalog), trace references/orphans, diff versions, or set up the script-XML round-trip.
argument-hint: "[command] [args] [options]"
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# FileMaker DDR → analyzable + agent-readable

A FileMaker **DDR** (Database Design Report) is a full XML dump of a database's structure — tables, fields, scripts, layouts, relationships, custom functions, value lists (no record data). This skill turns that multi-megabyte dump into two things:

1. **Per-object files** (`schema/parsed/<db>/<type>/…`) the analysis commands read.
2. **An agent-facing knowledge base** (`schema/readable/<db>/`) — the context an agent loads to read and *write* FileMaker script/calc XML for that specific database.

The engine lives in this project's `scripts/` folder and carries no client data. No credentials needed — fully offline.

## When

- You have a FileMaker schema export and need to understand or audit the system (tables, scripts, relationships, dependencies).
- You want to trace what references an object, find orphans, or diff two schema versions.
- You're standing up the **script-XML round-trip** (see the `fm-scripts` skill and `docs/guides/script_xml_roundtrip.md`). This skill produces the knowledge base that powers it.

## Two export formats — auto-detected

| Format | Looks like | Notes |
|---|---|---|
| **Classic DDR** (FM 12–22) | `File → Manage → Database Design Report → XML` → `<FMPReport>` + one XML per DB | The long-standing format. |
| **FM 2026 "Save a Copy as XML"** | `File → Save a Copy as → XML` → `Summary.xml` + a *folder* of split-catalog files (`<FMSaveAsXML split_catalogs="True">`) | **Preferred when available** — pre-resolved references (inline `TableOccurrenceReference`/`FieldReference`/`ScriptReference`), per-object change metadata, and a `DDR_INFO` text store with readable step text. Powers exact dependency tracing. |

`split` detects which it is. Hand it the `Summary.xml`, the catalog folder, or a single catalog file.

## Commands

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/tools/ddr/ddr.py <command> [args]
```

| Command | Does |
|---|---|
| `split <input> <parsed_dir>` | Parse the export into per-object files. **Run first.** |
| `summary <parsed_dir>` | Tables/fields/scripts/layouts/relationships overview + concerns. |
| `refs <parsed_dir> <target>` | Trace everything that references a target (`--type auto\|eds\|to\|field\|script\|layout\|valuelist`). |
| `orphans <parsed_dir>` | Unreferenced TOs/fields/scripts/layouts/CFs/value lists. |
| `compare <before> <after>` | Field-level diff of two parsed versions. |
| `search <parsed_dir> <term>` | Free-text/regex across calcs, scripts, layouts, etc. (`--regex`, `--case-sensitive`, `--type all\|calcs\|scripts\|layouts\|valuelists\|customfunctions`). |
| `readable <parsed_dir>` | **Export the agent knowledge base** (default output: `<parsed>/../readable/`). |

All commands accept `--output <path>` (save report) and `--json`. Starter conventions: raw exports in `schema/ddrs/YYYY-MM-DD/`, parsed output in `schema/parsed/`, knowledge base in `schema/readable/`, saved reports in `schema/reports/`.

## The agent knowledge base (`readable`)

`readable` writes, per database:

- `_schema.md` — table occurrences + relationship graph, every table's fields **with ids and types**, custom-function signatures, value lists, script + layout indexes. The file to load first; it has what's needed to emit a valid `<Field table="<TO>" id="<id>" name="<Field>"/>` and correct `TO::Field` calcs.
- `_xref.md` — reverse lookups: entry-point scripts, table → scripts that touch it, the script call graph.
- `custom_functions.md` — full custom-function bodies.
- `scripts/<folder>/<name>.md` — each script's **Connects to** / **Called by** dependency manifest (exact, from resolved references) + indented pseudo-code.

This is what makes the **script-XML round-trip** possible: an agent loads `readable/`, resolves every reference, and returns valid `fmxmlsnippet` to paste back into FileMaker. The paste formats themselves are covered by the vendored Kear skills (`filemaker-xml`, `filemaker-layout-xml`, `filemaker-field-xml`); validate snippets with `${CLAUDE_PLUGIN_ROOT}/tools/fmlint/validate_snippet.py` before pasting.

## Format craft notes (FM 2026 split-catalog)

If you extend the parser, the non-obvious bits (`fmsaveasxml.py`):

- Definitions live under `Structure/AddAction/<Catalog>`; `DDR_INFO` is a content-addressable text store keyed by `_<UUID>` elements that `<DDRREF>`s point at **by text content**, not by hash. Readable step text (`Set Variable [ … ]`) lives only there.
- `lxml` `append()` **moves** nodes — count source elements *before* extraction.
- Some catalogs (Accounts, CustomFunctions, PrivilegeSets, ExtendedPrivileges) nest items in an `<ObjectList>`; others list them directly.
- Fields map to tables **positionally** (per-table `<FieldCatalog>` has no name/id) — document order matches `BaseTableCatalog`.
- Scripts appear twice — a `ScriptCatalog` hierarchy (folders/names/ids) and a `StepsForScripts` section (step bodies); join by `id`.
- Layout folders are `<Layout isFolder="True">` markers in a flat list, not nesting.

See `docs/reference/ddr_xml_structure.md` for the full format spec (both classic and FM 2026).

## Files

- `${CLAUDE_PLUGIN_ROOT}/tools/ddr/ddr.py` — the CLI (split/summary/refs/orphans/compare/search/readable), self-contained.
- `scripts/ddr_xml_utils.py` — shared XML helpers.
- `scripts/fmsaveasxml.py` — FM 2026 split-catalog parser (invoked by `split`).
- `scripts/readable.py` — the knowledge-base exporter (invoked by `readable`).

> Engine provenance: synced from Joe's library skill `_agentic-2026/_library/skills/core-infrastructure/filemaker-ddr` (2026-07-02). When improving the engine, update the library copy too — or make this starter's copy the one true home and retire the library's.

Requires Python 3 + `lxml` (`pip install lxml`; falls back to `xml.etree` with reduced XPath).
