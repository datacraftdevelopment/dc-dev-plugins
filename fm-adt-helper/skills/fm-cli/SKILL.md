---
name: fm-cli
description: >
  Use when reading or editing a FileMaker .fmp12 file's structure with the ADT `fm` CLI —
  tables, fields, relations, table occurrences, value lists, custom functions, scripts,
  layouts, accounts, privilege sets, extended privileges, persistent data — on a local
  path or an fmnet:// hosted file. Also use for validating or evaluating FileMaker
  calculations from the shell, for headless data reads via ExecuteSQL when no MCP
  connector is available, for looking up an op's exact keys ("what does fm accept for
  field create"), and for interpreting fm errors (dbError 207/303/212/802, rolledBack,
  unknown-key refusals).
---

# The `fm` CLI — schema as transactional NDJSON

`fm` applies structure changes as a batch of NDJSON operations — one JSON object
per line in, one result line out — against a single database
(`--file=<path.fmp12|fmnet://host/Name>`). It embeds the real FileMaker engine,
so semantics are FileMaker's own. No FileMaker Pro, no handshake, no connector:
this is the schema lane, and it works even when everything else is down.

## Grammar

```
{"op":"<verb>:<catalog>", ...keys...}
```

Verbs: `create`, `read`, `update`, `delete` — plus `validate` and `evaluate` on
the `calculation` catalog only. 20 catalogs: account, authorization,
baseDirectory, calculation, customFunction, customMenu, customMenuSet,
extendedPrivilege, externalDataSource, field, font, graphNote, layout,
persistentData, privilegeSet, relation, script, table, tableOccurrence,
valueList.

Every op addresses things by **name**; every result reports FileMaker's **id**.
A missing name is an error with suggestions, never an auto-create.

## Don't memorize op shapes — the help tree is the contract

`fm help` is generated from the same schema the binary validates against, so it
cannot drift, and it needs no file and no credentials. **It is the authoritative
lookup — fetch it on the machine rather than trusting any embedded key list:**

- `fm help` — catalog roster
- `fm help field create options autoEnter` — exact keys, conditions, enums
- `fm help script steps "Set Variable"` — per-step key/slot table (~220 steps)
- `fm help script steps forms` — glossary of value forms (bareFlag, calc, enum…)
- `fm help --json --all` — the entire tree as one object (~448 nodes in 0.4.0)

**Error messages teach the API.** Unknown keys are refused (never ignored) and
the refusal lists every accepted key; wrong shapes name the wanted key. Probing
with `--dry-run` is a legitimate discovery loop.

## The discipline: dry-run → apply → fresh verify

1. Keep batches as numbered, re-runnable NDJSON files under `ops/`.
2. `--dry-run` first — it validates everything including cross-references (a
   dry-run field on a dry-run table resolves). Expect `errors: 0`.
3. Apply. A batch is **all-or-nothing by default** — one erroring op rolls back
   the whole batch (`--abort-on-error=false` keeps successes). **This applies
   to reads too**: one bad read in a batch of five → exit 1, `rolledBack: true`.
4. Trust only the closing `{"type":"summary",...}` line, then verify with a
   `read:` **from a fresh process** — same-run reads can show state a later
   failure rolls back.

## Shapes worth knowing cold

- Calc values in **field options** are objects, and `context` (a table
  occurrence) is **required** even for context-free formulas:
  `{"text":"Get ( UUID )","context":"Contact"}`. Layout-object calc settings
  (tooltips, hideCondition) are plain strings instead — two shapes for "a
  calculation" depending on where you are.
- Script step bodies are arrays of `{"stepID":<n>,"step":"<name>",...}` — both
  required and cross-checked. Calc slots are compiled at write time: syntax
  errors and unknown field names are refused, not stored. Literal strings in
  calc slots keep their quotes in the JSON (`"value":"\"Open\""`).
- `update:script` with a `body` requires the `token` from that script's
  `read … detail:true` — optimistic concurrency is mandatory for body swaps.
- Named reads return a single object; unnamed reads return
  `{total, returned, items:[...]}`.

## The no-handshake data-read trick

`evaluate:calculation` + `ExecuteSQL` = **headless data reads over the schema
lane**. The engine opens the file as a real client and evaluates for real —
joins, GROUP BY, even unstored cross-relation calcs. No sharing of the plugin
lane, no connector, works when the MCP is wedged or the screen is locked:

```
{"op":"evaluate:calculation","calculation":{"text":"ExecuteSQL ( \"SELECT ...\" ; \",\" ; \"¶\" )","context":"Contact"}}
```

## Credentials

`--username --keychain --prompt` is the canonical shape (native window, up to 3
tries, offers to save to the keychain). Passwords never touch the conversation.
A blank file's auto-login Admin needs nothing, including over fmnet.
`--store-credentials` requires a real terminal. **fm requires a full-access
account for everything** — a [Data Entry Only] account authenticates and then
gets dbError 207 even for reads.

## Error triage — discriminate on dbError, not message text

| dbError | Meaning | Move |
|---|---|---|
| 207 | Authenticated, no schema privilege | Terminal — get a full-access account |
| 303 | Schema locked by another session | Retry after they close Manage > Database |
| 212 | Credentials rejected | Fix credentials |
| 802 | File not being served | Per-file sharing is off — see `adt-connections` |

Layout-specific behavior and traps: `adt-native-layouts`. Surprises of every
flavor: `adt-quirks`.
