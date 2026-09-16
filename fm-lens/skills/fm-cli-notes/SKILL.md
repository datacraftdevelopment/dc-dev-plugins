---
name: fm-cli-notes
description: >
  Field notes that SUPPLEMENT Claris's own `fm-cli` skill (filemaker-agentic-development)
  — load that first for the op grammar, help tree, dry-run/apply/fresh-read discipline and
  credentials. Use this for what Claris doesn't cover: headless data reads through
  evaluate:calculation + ExecuteSQL when no MCP connector is available, the two calc
  shapes, script-step and update:script shape traps, and triaging fm errors by dbError
  (207 with a Data Entry account, 303, 212, 802).
---

# `fm` field notes: what Claris's `fm-cli` skill leaves out

Claris's `fm-cli` skill is the primary guide: grammar, `fm help` as the
contract, dry-run → apply → verify from a fresh process, credentials, and ops
files as scratch that nothing replays. This skill keeps only what the helper
learned that the Claris skill doesn't say. Re-checked on every new ADT build
(`fm-ADT-testing/docs/helper-gap-ledger.md`); anything Claris starts covering
gets deleted here.

## Shapes worth knowing cold

- Calc values in **field options** are objects, and `context` (a table
  occurrence) is **required** even for context-free formulas:
  `{"text":"Get ( UUID )","context":"Contact"}`. Layout-object calc settings
  (tooltips, hideCondition) are plain strings instead, so "a calculation" has
  two shapes depending on where it sits. A tooltip literal still needs its
  own quotes: `"tooltip":"\"hello\""`.
- Script step bodies are arrays of `{"stepID":<n>,"step":"<name>",...}`. From
  0.7.0 the two are **cross-checked and a disagreement is refused** (quirk
  104), so take ids and enum spellings from `fm help --json --all`
  (`script/steps/<name>`), never from memory. Calc slots are compiled at
  write time: syntax errors and unknown field names are refused, not stored.
  Literal strings keep their quotes in the JSON (`"value":"\"Open\""`).
- `update:script` with a `body` requires the `token` from that script's
  `read … detail:true`. Optimistic concurrency is mandatory for body swaps.
- Named reads return a single object; unnamed reads return
  `{total, returned, items:[...]}`.
- Layout objects only draw once the layout's theme is assigned through `fm`.
  See `adt-native-layouts` (quirk 106).

## The no-handshake data-read trick

`evaluate:calculation` + `ExecuteSQL` gives **headless data reads over the
schema lane**. The engine opens the file as a real client and evaluates for
real: joins, GROUP BY, even unstored cross-relation calcs. It needs no plug-in
lane and no connector, and it works when the MCP is wedged or the screen is
locked:

```
{"op":"evaluate:calculation","calculation":{"text":"ExecuteSQL ( \"SELECT ...\" ; \",\" ; \"¶\" )","context":"Contact"}}
```

A table created in the same batch can't be the `context` (DBError 8309).

## Error triage: discriminate on dbError, not message text

| dbError | Meaning | Move |
|---|---|---|
| 207 | Authenticated, no schema privilege. **fm needs a full-access account for everything**: a [Data Entry Only] account signs in and still gets 207, even for reads | Terminal: get a full-access account |
| 303 | Schema locked by another session | Retry after they close Manage > Database |
| 212 | Credentials rejected | Fix credentials |
| 802 | File not being served | Per-file sharing is off; see `adt-connections` |

Layout behaviour and traps: `adt-native-layouts`. What works on the
installed build: `adt-capabilities`. Surprises of every kind: `adt-quirks`.
