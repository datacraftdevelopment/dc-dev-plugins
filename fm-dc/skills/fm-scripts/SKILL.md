---
name: fm-scripts
description: Read, write, and modify FileMaker scripts and calculations as XML against THIS project's database. Use when the user pastes FileMaker script XML (fmxmlsnippet) and wants it changed, asks "write a script that…", asks what a script does or "what does X connect to / what calls X", or wants a calculation built/fixed with real schema awareness. Powers the paste-in → updated-XML round trip using the project's generated knowledge base.
argument-hint: "[paste a script, or describe what you want]"
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# FileMaker Scripts — Schema-Aware Round-Trip

This skill lets you read, write, and modify FileMaker scripts/calculations for **this
project's specific database**, using a generated knowledge base so every `TO::Field`,
script call, and custom function is resolved against the real schema. The output is
`fmxmlsnippet` XML the user pastes straight back into FileMaker.

## The knowledge base (load this first)

Everything you need is under **`schema/readable/<db>/`** (generated from the DDR):

| File | Use it to… |
|---|---|
| `_schema.md` | Resolve any `TO::Field`; get the field **id** + a valid table-occurrence name for a Set Field; check field types; find script/layout names + ids. **Always load before writing XML.** |
| `_xref.md` | Answer "what calls X?", "what touches table Y?", find entry points (reverse lookups). |
| `custom_functions.md` | Read full custom-function bodies before using or editing them. |
| `scripts/<folder>/<name>.md` | Read an existing script: its **Connects to** / **Called by** header (exact dependencies) + indented pseudo-code. |

**If `schema/readable/` is missing or stale**, generate it first:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/tools/ddr/ddr.py split schema/ddrs/<date>/Summary.xml schema/parsed/
python3 ${CLAUDE_PLUGIN_ROOT}/tools/ddr/ddr.py readable schema/parsed/
```

Needs a schema export (classic DDR or FM 2026 Save-as-XML — auto-detected); see the `ddr` skill.

## The four tasks this supports

1. **Answer questions about scripts** — read the script's `scripts/<name>.md` (deps + pseudo-code) and `_xref.md`. Cite exact tables/fields/called-scripts; don't guess.
2. **Modify a pasted script** — the user pastes `fmxmlsnippet`. Resolve every reference against `_schema.md`, make the change, return updated `fmxmlsnippet`.
3. **Backtrack what a script connects to, then update it** — start from the script's `Connects to` block + `_xref.md` to understand impact, then return the updated XML.
4. **Write a script from scratch** — compose from `_schema.md` + `custom_functions.md` + the step format.

## Writing valid paste-back XML

The paste format is `fmxmlsnippet` (clipboard format) — **NOT** the DDR/`FMSaveAsXML` export
format the knowledge base was built from. For the exact element structure, step type IDs,
and worked examples, **use the vendored `filemaker-xml` skill** — do not
reinvent the format. Non-negotiables:

- Root is `<fmxmlsnippet type="FMObjectList">`; each step `<Step enable= id= name=>`.
- **Set Field:** `<Field table="<TO name>" id="<field id>" name="<Field>"/>` — `table` is a
  **table occurrence**, not a base table. Pull the id from `_schema.md`.
- Calculations go in `<![CDATA[ … ]]>`; inside CDATA use raw `&` (not `&amp;`).
- Use `<>` not `≠` in calcs. Comments are step id 89. Set Variable 141, Set Field 76, If 68.
- Preserve FileMaker's real quirks (e.g. `<AccoutName>` misspelling in Configure AI Account).

## Always validate before returning XML

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/tools/fmlint/validate_snippet.py <file>     # fmlint package: ${CLAUDE_PLUGIN_ROOT}/tools/fmlint
```

Catches unbalanced If/Loop blocks, unknown step names, unclosed calculations. Fix issues
before handing XML back. (See `docs/guides/validate_snippet.md`.)

## Workflow at a glance

1. User copies steps in FileMaker → clipboard holds `fmxmlsnippet` → pastes to you (or asks you to write one).
2. Load `schema/readable/<db>/_schema.md` (+ `_xref.md` / `custom_functions.md` / a specific `scripts/*.md` as needed).
3. Make the change / write the script, resolving all references against the schema.
4. Validate the `fmxmlsnippet`, then return it for the user to paste back into FileMaker.

Full SOP with examples: `docs/guides/script_xml_roundtrip.md`.

## Critical rules

1. **Resolve, don't guess.** Every field/TO/script/custom-function reference must exist in
   `_schema.md` / `custom_functions.md`. If you can't find it, say so — don't invent names.
2. **Table occurrences, not base tables**, in calcs and Set Field `table=`.
3. **Validate before returning** any `fmxmlsnippet`.
4. **You produce XML; you don't change FileMaker.** The user pastes it in.
5. **Regenerate the KB after a schema change** (new DDR → `ddr split` → `ddr readable`), or
   your references will be stale.
