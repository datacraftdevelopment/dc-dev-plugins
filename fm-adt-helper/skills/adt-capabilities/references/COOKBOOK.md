# ADT cookbook — verified on fm-cli 0.7.0

Every recipe below is the literal NDJSON from a test case that **passed on this build**, at the tier its row names. Nothing is here from memory: if a recipe stops working, its test fails and the recipe leaves this file on the next run.

Generated 2026-09-16T15:24:34 — do not hand-edit. Add a recipe by adding a passing case under `tests/suites/`.

## Contents

- **calculation** — Check a formula compiles before writing it anywhere, Evaluate a calculation from the shell, Read FileMaker data headlessly, with no connector, Tell whether a formula is valid
- **customFunction** — Create a custom function
- **customMenu** — Create a custom menu set
- **field** — Annotate a field for AI and OData, Attach a custom validation message, Auto-enter Get(UUID), Auto-enter a constant, Auto-enter a creation timestamp, Auto-enter a looked-up value, Auto-enter a serial number, Auto-enter the modifying account, Comment a field, Constrain a field to a range, Create a calculated field, Create a global field, Create a repeating field, Index a field, Limit a field's length, Require a four-digit year, Require a unique value, Require a value
- **layout** — Add a button bar, Add a button to a layout, Add a field to a layout, Add a group to a layout, Add a label to a layout, Add a line to a layout, Add a oval to a layout, Add a popoverButton to a layout, Add a portal to a layout, Add a rectangle to a layout, Add a roundedRectangle to a layout, Add a slideControl to a layout, Add a tabControl to a layout, Add a webViewer to a layout, Build a layout with header, sub-summary and footer parts, Configure an object after placing it (the two-step), Give a button its tooltip in the same op that places it, Put content inside a tab panel, Resize a portal and its row contents, Set a layout script trigger, Set a layout's print columns, page margins and row height, Wire a button to a script
- **multifile** — Add a table from another FileMaker file to the graph, Data separation: a UI file over a data file, Give a data source a hosted path with a local fallback, Join a local table to a table in another file, Register another FileMaker file as a data source, Show a field from another file on a layout
- **persistentData** — Deploy a web viewer app over the schema lane
- **relation** — Create a relationship and a calc that travels it, in one batch, Relate two tables, Relate two tables with cascade delete, Sort a relationship's related records by a named field
- **script** — Create a script
- **script-step** — Call a plug-in function from an fm-authored script
- **security** — Create a limited account, Grant an extended privilege
- **table** — Rename a table
- **theme** — Derive a custom theme from the file's own and regroup it
- **valueList** — Create a value list

## calculation

### Check a formula compiles before writing it anywhere

Verified: **accepted**

> Cheaper than a dry-run create, and the same check the engine applies when a calc is stored in a field or a script slot.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "C"}
{"op": "create:field", "table": "C", "name": "Name", "type": "text"}
{"op": "create:field", "table": "C", "name": "Amount", "type": "number"}
```

```json
{"op": "validate:calculation", "calculation": "Upper ( Name )", "context": "C"}
```

### Evaluate a calculation from the shell

Verified: **accepted** · regression-tests quirk 76

> Here `calculation` is a PLAIN STRING with `context` as a sibling key. In FIELD OPTIONS the same idea is an object {text, context}; on a LAYOUT OBJECT (tooltip, hideCondition) it is a bare string with no context at all. Three shapes -- check which surface you are on (quirks 9, 76).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "C"}
{"op": "create:field", "table": "C", "name": "Name", "type": "text"}
{"op": "create:field", "table": "C", "name": "Amount", "type": "number"}
```

```json
{"op": "evaluate:calculation", "calculation": "1 + 1", "context": "C"}
```

### Read FileMaker data headlessly, with no connector

Verified: **accepted** · regression-tests quirk 33

> This is the lane that survives everything: it needs no file sharing, no MCP handshake, no plug-in and no unlocked screen, so it is the only safe basis for unattended work (quirks 33, 37, 46). It opens the file as a real client, so unstored cross-relation calcs evaluate correctly (quirk 27).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "C"}
{"op": "create:field", "table": "C", "name": "Name", "type": "text"}
{"op": "create:field", "table": "C", "name": "Amount", "type": "number"}
```

```json
{"op": "evaluate:calculation", "context": "C", "calculation": "ExecuteSQL ( \"SELECT COUNT(*) FROM C\" ; \"\" ; \"\" )"}
```

### Tell whether a formula is valid

Verified: **accepted** · regression-tests quirk new

> Branch on `result.valid`, NEVER on `status`. A formula that does not compile still returns status "ok" and exit 0, because the question -- is this valid? -- was answered; the answer is valid:false, with the engine's code and the character offsets in result.error. status "error" here means something else entirely: the question could not be asked at all, e.g. an unknown `context` occurrence. The CLI ships this warning in the result itself.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "C"}
{"op": "create:field", "table": "C", "name": "Name", "type": "text"}
{"op": "create:field", "table": "C", "name": "Amount", "type": "number"}
```

```json
{"op": "validate:calculation", "calculation": "Upper ( ", "context": "C"}
```

## customFunction

### Create a custom function

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:customFunction", "name": "Double", "parameters": ["n"], "body": "n * 2"}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:customFunction", "name": "Double", "detail": true}
```

## customMenu

### Create a custom menu set

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:customMenu", "name": "AgentMenu"}
{"op": "create:customMenuSet", "name": "AgentSet", "menus": ["AgentMenu"]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:customMenu"}
{"op": "read:customMenuSet"}
```

## field

### Annotate a field for AI and OData

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_ai-annotation", "type": "text", "options": {"aiAnnotation": "The person's display name"}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_ai-annotation", "detail": true}
```

### Attach a custom validation message

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_validation-message", "type": "text", "options": {"validation": {"notEmpty": true, "message": "Name is required"}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_validation-message", "detail": true}
```

### Auto-enter Get(UUID)

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_uuid", "type": "text", "options": {"autoEnter": {"type": "calc", "calculation": {"text": "Get ( UUID )", "context": "A"}}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_uuid", "detail": true}
```

### Auto-enter a constant

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_constant", "type": "text", "options": {"autoEnter": {"type": "constant", "constant": "Open"}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_constant", "detail": true}
```

### Auto-enter a creation timestamp

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_timestamp-created", "type": "text", "options": {"autoEnter": {"type": "variable", "variable": "creationTimestamp"}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_timestamp-created", "detail": true}
```

### Auto-enter a looked-up value

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
{"op": "create:relation", "left": "A", "right": "B", "predicates": [{"leftField": "Id", "op": "=", "rightField": "AId"}]}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_lookup", "type": "text", "options": {"autoEnter": {"type": "lookup", "lookup": {"source": {"occurrence": "B", "field": "Amount"}, "context": "A", "onNoMatch": "nextHigher"}}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_lookup", "detail": true}
```

### Auto-enter a serial number

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_serial", "type": "text", "options": {"autoEnter": {"type": "serial", "next": "1", "increment": 1, "prohibitModification": true}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_serial", "detail": true}
```

### Auto-enter the modifying account

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_account-modified", "type": "text", "options": {"autoEnter": {"type": "variable", "variable": "modifierAccount"}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_account-modified", "detail": true}
```

### Comment a field

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_comment", "type": "text", "options": {"comment": "A note for developers"}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_comment", "detail": true}
```

### Constrain a field to a range

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_range", "type": "text", "options": {"validation": {"range": {"min": "A", "max": "M"}}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_range", "detail": true}
```

### Create a calculated field

Verified: **on disk** · regression-tests quirk 9

> A calculation in FIELD OPTIONS is an object with a mandatory `context`, even for a context-free formula like Get(UUID). Layout-object calcs are plain strings, and evaluate:calculation takes a plain string with `context` as a sibling key -- three shapes (quirks 9, 76).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Upper", "type": "text", "options": {"fieldType": "calculated", "calculation": {"text": "Upper ( Name )", "context": "A"}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Upper", "detail": true}
```

### Create a global field

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_global", "type": "text", "options": {"global": true}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_global", "detail": true}
```

### Create a repeating field

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_repetitions", "type": "text", "options": {"repetitions": 4}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_repetitions", "detail": true}
```

### Index a field

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_indexing", "type": "text", "options": {"indexing": "all"}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_indexing", "detail": true}
```

### Limit a field's length

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_max-length", "type": "text", "options": {"validation": {"maxLength": 40}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_max-length", "detail": true}
```

### Require a four-digit year

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_four-digit-year", "type": "text", "options": {"validation": {"strictFourDigitYear": true}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_four-digit-year", "detail": true}
```

### Require a unique value

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_unique", "type": "text", "options": {"validation": {"unique": true}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_unique", "detail": true}
```

### Require a value

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:field", "table": "A", "name": "Opt_not-empty", "type": "text", "options": {"validation": {"notEmpty": true, "strict": true}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Opt_not-empty", "detail": true}
```

## layout

### Add a button bar

Verified: **on disk** · regression-tests quirk 72

> Give the BAR bounds and list the segments in `objects` with no bounds of their own. Segments read back as {0,0,0,0}: that is a REPORTING artifact, not a defect. The CLI is explicit that a segment's rectangle is the bar's divided by the segment count and 'is not stored at all' -- passing per-segment bounds is refused with invalid_field, and so is updateObjects on a segment's bounds. Change segment width by resizing the bar or changing the number of segments. This CORRECTS quirk 72, which read the zero bounds as the reason button bars never rendered.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "buttonBar", "bounds": {"left": 20, "top": 20, "width": 300, "height": 40}, "objects": [{"type": "button", "text": "A"}, {"type": "button", "text": "B"}, {"type": "button", "text": "C"}]}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a button to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "button", "bounds": {"left": 20, "top": 20, "width": 200, "height": 30}, "objectName": "probe_button", "text": "Go"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a field to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "field", "bounds": {"left": 20, "top": 30, "width": 200, "height": 30}, "objectName": "probe_field", "field": "UI::Name", "label": ""}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a group to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "group", "bounds": {"left": 20, "top": 35, "width": 200, "height": 30}, "objectName": "probe_group"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a label to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "label", "bounds": {"left": 20, "top": 40, "width": 200, "height": 30}, "objectName": "probe_label", "text": "A label"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a line to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "line", "bounds": {"left": 20, "top": 45, "width": 200, "height": 30}, "objectName": "probe_line"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a oval to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "oval", "bounds": {"left": 20, "top": 50, "width": 200, "height": 30}, "objectName": "probe_oval"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a popoverButton to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "popoverButton", "bounds": {"left": 20, "top": 55, "width": 200, "height": 30}, "objectName": "probe_popoverButton", "text": "Pop"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a portal to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "portal", "bounds": {"left": 20, "top": 200, "width": 400, "height": 120}, "objectName": "probe_portal", "tableOccurrence": "UIChild", "rows": 4}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a rectangle to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "rectangle", "bounds": {"left": 20, "top": 65, "width": 200, "height": 30}, "objectName": "probe_rectangle"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a roundedRectangle to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "roundedRectangle", "bounds": {"left": 20, "top": 70, "width": 200, "height": 30}, "objectName": "probe_roundedRectangle"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a slideControl to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "slideControl", "bounds": {"left": 20, "top": 470, "width": 400, "height": 100}, "objectName": "probe_slideControl", "objects": [{"type": "slidePanel"}, {"type": "slidePanel"}]}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a tabControl to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "tabControl", "bounds": {"left": 20, "top": 340, "width": 400, "height": 120}, "objectName": "probe_tabControl", "objects": [{"type": "tabPanel", "title": "One"}, {"type": "tabPanel", "title": "Two"}]}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Add a webViewer to a layout

Verified: **on disk**

> Only these 23 keys are legal at add time: type, bounds, objectName, field, label, text, tableOccurrence, rows, objects, url, urlCalculation, allowInteraction, displayInFindMode, showProgressBar, showStatusMessages, encodeUrl, allowJavaScriptToPerformScripts, anchors, action, parent, title, picture. Everything else is a follow-up updateObjects.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "webViewer", "bounds": {"left": 20, "top": 85, "width": 200, "height": 30}, "objectName": "probe_webViewer", "url": "https://example.invalid"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Build a layout with header, sub-summary and footer parts

Verified: **on disk** · regression-tests quirk 18 (lifted in 0.7.0, see quirk 100)

> Parts were entirely absent through 0.6.0 (quirk 18) -- an object below the lowest part used to land nowhere addressable. 0.7.0 adds `parts` on create:layout and `addParts`/`removeParts` on update:layout, and now moves an object below the lowest part back inside it instead of losing it. See quirk 100.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "create:layout", "name": "Parted", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 300, "parts": [{"type": "header", "height": 40}, {"type": "leadingSubSummary", "breakField": "UI::Name", "height": 30}, {"type": "body"}, {"type": "trailingSubSummary", "breakField": "UI::Name", "height": 30}, {"type": "footer", "height": 40}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Parted", "detail": true}
```

### Configure an object after placing it (the two-step)

Verified: **on disk** · regression-tests quirk 9, 14

> addObjects then updateObjects, addressing the object by the id from createdObjectIds. Object ids on a fresh layout start at 1 and are NOT returned in input order -- read them back rather than assuming (quirk 14). Calc-valued keys here (tooltip, hideCondition) are plain JSON strings whose CONTENT is a calculation, so a literal tooltip needs embedded quotes: "\"Hello\"", not "Hello". Bare prose is refused with DBError 106 because the engine reads it as field names. That is a third shape again -- field options want a {text, context} object (quirk 9), evaluate:calculation wants a plain string with a sibling context (quirk 76).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "field", "bounds": {"left": 20, "top": 20, "width": 200, "height": 30}, "field": "UI::Name", "label": "", "objectName": "nameField"}]}
{"op": "update:layout", "name": "Main", "updateObjects": [{"id": 1, "tooltip": "\"The contact's name\"", "control": "dropDownList", "valueList": "Colours", "placeholderText": "\"Pick one\"", "accessibilityTitle": "\"Name field\"", "hideCondition": "Get ( AccountName ) = \"nobody\""}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Give a button its tooltip in the same op that places it

Verified: **on disk** · regression-tests quirk 102

> `tooltip` is a CALCULATION slot, exactly like Pro's own Set Tooltip dialog -- a literal string must be quoted (`"hello"`) or it is refused as 'not a valid calculation' (DBError 106) rather than stored as text. New in 0.7.0 -- see quirk 100.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "button", "bounds": {"left": 20, "top": 20, "width": 200, "height": 30}, "text": "Go", "tooltip": "\"hello\""}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Put content inside a tab panel

Verified: **on disk** · regression-tests quirk 12, 13

> Two ops. The panel ids come from the first op's createdObjectIds -- read them back rather than guessing, since they are not in input order. A field placed inside a container also drags its ~208pt auto-label into the bounds check, so pass label:"" or leave 210pt of room on the left (quirk 13).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "tabControl", "bounds": {"left": 20, "top": 20, "width": 400, "height": 200}, "objects": [{"type": "tabPanel", "title": "One"}, {"type": "tabPanel", "title": "Two"}]}]}
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "label", "text": "inside", "parent": 2, "bounds": {"left": 220, "top": 40, "width": 150, "height": 24}}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Resize a portal and its row contents

Verified: **on disk** · regression-tests quirk 60, 75

> A child's bounds are RELATIVE to the container's top-left (the error reports the usable interior, e.g. 'starts at -1pt,-1pt and is 400pt by 30pt'), while a top-level object's bounds are absolute on the layout. Put the portal entry FIRST in the updateObjects array and always send `rows` alongside `height` -- row height is re-derived as height/rows on any height change, so a bounds-only shrink silently narrows the rows and the next inner-field update is refused with the row interior named in the error.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "portal", "tableOccurrence": "UIChild", "rows": 6, "bounds": {"left": 20, "top": 20, "width": 400, "height": 180}}]}
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "field", "field": "UIChild::Label", "label": "", "parent": 1, "bounds": {"left": 0, "top": 0, "width": 200, "height": 28}}]}
{"op": "update:layout", "name": "Main", "updateObjects": [{"id": 1, "rows": 4, "bounds": {"left": 20, "top": 20, "width": 400, "height": 200}}, {"id": 2, "bounds": {"left": 0, "top": 0, "width": 200, "height": 44}}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Set a layout script trigger

Verified: **on disk**

> Never attach a Show Custom Dialog to a trigger on an agent-managed file: the modal starves FileMaker's idle loop and wedges every other lane (quirks 6, 55).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "setTriggers": [{"event": "OnLayoutEnter", "script": "Noop"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Set a layout's print columns, page margins and row height

Verified: **on disk**

> New in 0.7.0, alongside `baseWidth`/`bodyHeight` sizing the layout itself. All three keys (`printColumns`, `pageMargins`, `rowHeight`) are `clearable`: send null to let the printer/theme decide instead of a fixed value.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "printColumns": {"count": 2, "width": 250}, "pageMargins": {"left": 36, "top": 36, "right": 36, "bottom": 36}, "rowHeight": 20}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

### Wire a button to a script

Verified: **on disk**

> `action` takes exactly ONE script-step object, using the same vocabulary as a script body.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "UI"}
{"op": "create:field", "table": "UI", "name": "Name", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Note", "type": "text"}
{"op": "create:table", "name": "UIChild"}
{"op": "create:field", "table": "UIChild", "name": "Label", "type": "text"}
{"op": "create:field", "table": "UIChild", "name": "ParentId", "type": "text"}
{"op": "create:field", "table": "UI", "name": "Id", "type": "text"}
{"op": "create:relation", "left": "UI", "right": "UIChild", "predicates": [{"leftField": "Id", "op": "=", "rightField": "ParentId"}]}
{"op": "create:valueList", "name": "Colours", "type": "custom", "values": ["Red", "Green", "Blue"]}
{"op": "create:script", "name": "Noop", "body": [{"stepID": 89, "step": "#", "text": "noop"}]}
{"op": "create:layout", "name": "Main", "tableOccurrence": "UI", "baseWidth": 700, "bodyHeight": 600}
```

```json
{"op": "update:layout", "name": "Main", "addObjects": [{"type": "button", "bounds": {"left": 20, "top": 20, "width": 200, "height": 30}, "text": "Run it", "action": {"stepID": 1, "step": "Perform Script", "script": "Noop"}}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "Main", "detail": true}
```

## multifile

### Add a table from another FileMaker file to the graph

Verified: **on disk** · regression-tests quirk 91

> Nothing validates `tableId`: a wrong one creates an occurrence that dangles. Every file numbers tables from 129. Reads report `resolved:false` because the CLI never opens the other file (quirk 91).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "Orders"}
{"op": "create:field", "table": "Orders", "name": "SKU", "type": "text"}
{"op": "create:field", "table": "Orders", "name": "Qty", "type": "number"}
{"op": "create:externalDataSource", "name": "Data", "paths": ["file:{{Data}}"]}
```

```json
{"op": "create:tableOccurrence", "name": "Data_Items", "dataSource": "Data", "tableId": 129, "graph": {"bounds": {"left": 400, "top": 40, "width": 180, "height": 160}, "color": "#4A90D9"}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:tableOccurrence", "name": "Data_Items", "detail": true}
```

### Data separation: a UI file over a data file

Verified: **on disk** · regression-tests quirk 91

> Read the data file's table and field ids first and carry an id map; every external field on every UI layout is placed by id (quirk 91). Give the data file at least one layout, or Pro cannot open it when the UI file references it.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "Globals"}
{"op": "create:field", "table": "Globals", "name": "gFilter", "type": "text", "options": {"global": true}}
{"op": "create:externalDataSource", "name": "Data", "paths": ["file:{{Data}}"]}
```

```json
{"op": "create:tableOccurrence", "name": "Items", "dataSource": "Data", "tableId": 129, "graph": {"bounds": {"left": 40, "top": 40, "width": 180, "height": 160}}}
{"op": "create:tableOccurrence", "name": "Vendors", "dataSource": "Data", "tableId": 130, "graph": {"bounds": {"left": 400, "top": 40, "width": 180, "height": 160}}}
{"op": "create:relation", "left": "Items", "right": "Vendors", "predicates": [{"leftFieldId": 4, "op": "=", "rightFieldId": 2}]}
{"op": "create:layout", "name": "Item List", "tableOccurrence": "Items", "baseWidth": 700, "bodyHeight": 300, "objects": [{"type": "field", "fieldOccurrence": "Items", "fieldId": 1, "objectName": "sku", "bounds": {"left": 20, "top": 20, "width": 150, "height": 24}}, {"type": "field", "fieldOccurrence": "Items", "fieldId": 2, "objectName": "description", "bounds": {"left": 190, "top": 20, "width": 300, "height": 24}}, {"type": "field", "fieldOccurrence": "Vendors", "fieldId": 1, "objectName": "vendor", "bounds": {"left": 20, "top": 60, "width": 300, "height": 24}}]}
{"op": "create:layout", "name": "Vendor Detail", "tableOccurrence": "Vendors", "baseWidth": 700, "bodyHeight": 300, "objects": [{"type": "field", "fieldOccurrence": "Vendors", "fieldId": 1, "objectName": "name", "bounds": {"left": 20, "top": 20, "width": 300, "height": 24}}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:tableOccurrence", "detail": true}
{"op": "read:layout"}
```

### Give a data source a hosted path with a local fallback

Verified: **on disk** · regression-tests quirk 92

> `fmnet://host/File` with two slashes is REJECTED by the engine; the stored form is `fmnet:/host/File` (quirk 92).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "Orders"}
{"op": "create:field", "table": "Orders", "name": "SKU", "type": "text"}
{"op": "create:field", "table": "Orders", "name": "Qty", "type": "number"}
{"op": "create:externalDataSource", "name": "Data", "paths": ["file:{{Data}}"]}
```

```json
{"op": "update:externalDataSource", "name": "Data", "paths": ["fmnet:/fms.example.com/Data", "file:{{Data}}"]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:externalDataSource", "name": "Data"}
```

### Join a local table to a table in another file

Verified: **on disk** · regression-tests quirk 91

> The far field is named by ID (`rightFieldId`), because a NAME only becomes a key by lookup in the other file's catalog and the CLI does not open it.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "Orders"}
{"op": "create:field", "table": "Orders", "name": "SKU", "type": "text"}
{"op": "create:field", "table": "Orders", "name": "Qty", "type": "number"}
{"op": "create:externalDataSource", "name": "Data", "paths": ["file:{{Data}}"]}
{"op": "create:tableOccurrence", "name": "Data_Items", "dataSource": "Data", "tableId": 129, "graph": {"bounds": {"left": 400, "top": 40, "width": 180, "height": 160}, "color": "#4A90D9"}}
```

```json
{"op": "create:relation", "left": "Orders", "right": "Data_Items", "predicates": [{"leftField": "SKU", "op": "=", "rightFieldId": 1}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:relation"}
```

### Register another FileMaker file as a data source

Verified: **on disk**

> `paths` is ordered and tried in sequence; a hosted path is single-slash `fmnet:/host/File` (quirk 92). Nothing is resolved at create time.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "Orders"}
{"op": "create:field", "table": "Orders", "name": "SKU", "type": "text"}
{"op": "create:field", "table": "Orders", "name": "Qty", "type": "number"}
```

```json
{"op": "create:externalDataSource", "name": "Data", "paths": ["file:{{Data}}"]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:externalDataSource", "name": "Data"}
```

### Show a field from another file on a layout

Verified: **on disk** · regression-tests quirk 91

> External fields are placed by `fieldOccurrence` + `fieldId`, never by name (quirk 91). The CLI warns that the Data API reads such a field only through a related occurrence.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "Orders"}
{"op": "create:field", "table": "Orders", "name": "SKU", "type": "text"}
{"op": "create:field", "table": "Orders", "name": "Qty", "type": "number"}
{"op": "create:externalDataSource", "name": "Data", "paths": ["file:{{Data}}"]}
{"op": "create:tableOccurrence", "name": "Data_Items", "dataSource": "Data", "tableId": 129, "graph": {"bounds": {"left": 400, "top": 40, "width": 180, "height": 160}, "color": "#4A90D9"}}
{"op": "create:relation", "left": "Orders", "right": "Data_Items", "predicates": [{"leftField": "SKU", "op": "=", "rightFieldId": 1}]}
```

```json
{"op": "create:layout", "name": "OrderEntry", "tableOccurrence": "Orders", "baseWidth": 700, "bodyHeight": 400, "objects": [{"type": "field", "field": "Orders::SKU", "objectName": "sku", "bounds": {"left": 20, "top": 20, "width": 200, "height": 24}}, {"type": "field", "fieldOccurrence": "Data_Items", "fieldId": 2, "objectName": "description", "bounds": {"left": 20, "top": 60, "width": 300, "height": 24}}, {"type": "portal", "tableOccurrence": "Data_Items", "objectName": "items", "rows": 5, "bounds": {"left": 20, "top": 100, "width": 400, "height": 150}, "objects": [{"type": "field", "fieldOccurrence": "Data_Items", "fieldId": 3, "bounds": {"left": 0, "top": 0, "width": 100, "height": 24}}]}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:layout", "name": "OrderEntry", "detail": true}
```

## persistentData

### Deploy a web viewer app over the schema lane

Verified: **on disk** · regression-tests quirk 40

> A ~400KB HTML bundle round-trips through persistentData with no connector, no handshake and no `adt deploy` -- which makes it lock-proof and usable unattended (quirk 40). On a HOSTED file the equivalent lane is a one-record App::html table over OData (quirk 64).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:persistentData", "instance": "suite", "key": "html", "value": "<html><body>xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx... [400,026 chars total, truncated for display]"}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:persistentData", "instance": "suite", "key": "html"}
```

## relation

### Create a relationship and a calc that travels it, in one batch

Verified: **on disk** · regression-tests quirk 10

> Quirk 10 said this had to be split across two fm invocations because a same-batch context answered dbError 106. On fm-cli 0.4.0 it works in one batch, occurrence and all. If this case ever starts failing again, the split is the workaround: occurrences and relations first, then the calc fields that travel them -- and note that calc fields referencing OTHER calc fields still need repeated passes, a fixpoint rather than one deferral (quirk 42).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:tableOccurrence", "name": "B2", "table": "B"}
{"op": "create:relation", "left": "A", "right": "B2", "predicates": [{"leftField": "Id", "op": "=", "rightField": "AId"}]}
{"op": "create:field", "table": "A", "name": "Total", "type": "number", "options": {"fieldType": "calculated", "calculation": {"text": "Sum ( B2::Amount )", "context": "A"}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:field", "table": "A", "name": "Total", "detail": true}
```

### Relate two tables

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:relation", "left": "A", "right": "B", "predicates": [{"leftField": "Id", "op": "=", "rightField": "AId"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:relation"}
```

### Relate two tables with cascade delete

Verified: **on disk** · regression-tests quirk 11

> `sortRelated` is a bare boolean -- the sort SPEC (which field, which direction) is not in the surface at all (quirk 11).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:relation", "left": "A", "right": "B", "predicates": [{"leftField": "Id", "op": "=", "rightField": "AId"}], "leftToRight": {"createRelated": true, "cascadeDelete": true, "sortRelated": true}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:relation"}
```

### Sort a relationship's related records by a named field

Verified: **on disk** · regression-tests quirk 11 (lifted in 0.7.0, see quirk 100)

> `sortSpec.fields` is the sort order itself and `sortRelated` is only its switch -- one stored structure, the same shape create:script's Sort Records step takes. Addressable via `leftToRight`/`rightToLeft` (named by traversal) or `onLeftTable`/`onRightTable` (named by the table the flags govern). This boundary held through 0.6.0 (quirk 11); 0.7.0 lifts it -- see quirk 100.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:relation", "left": "A", "right": "B", "predicates": [{"leftField": "Id", "op": "=", "rightField": "AId"}], "leftToRight": {"sortRelated": true, "sortSpec": {"fields": [{"field": "B::Amount", "order": "descending"}], "maintain": true}}}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:relation"}
```

## script

### Create a script

Verified: **on disk**

> Every step needs BOTH `stepID` and `step`, and they are cross-checked. Calculation slots are compiled at write time, so a literal string needs its quotes inside the JSON string: "value": "\"Open\"".

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:script", "name": "Hello", "body": [{"stepID": 89, "step": "#", "text": "a comment"}, {"stepID": 141, "step": "Set Variable", "name": "$x", "value": "1 + 1"}, {"stepID": 86, "step": "Set Error Capture", "on": true}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:script", "name": "Hello", "detail": true}
```

## script-step

### Call a plug-in function from an fm-authored script

Verified: **on disk** · regression-tests quirk 32

> The headless engine loads no plug-ins, so MBS(...) and ADTH_...(...) are refused as unknown functions. Evaluate() defers resolution to runtime, where FileMaker Pro does have the plug-in loaded.

```json
{"op": "create:script", "name": "Plug", "body": [{"stepID": 141, "step": "Set Variable", "name": "$v", "value": "Evaluate ( \"ADTH_Version\" )"}]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:script", "name": "Plug", "detail": true}
```

## security

### Create a limited account

Verified: **on disk** · regression-tests quirk 43

> fm itself needs FULL access for everything, including reads -- a [Data Entry Only] account authenticates and then fails the schema lock with dbError 207 (quirk 43). This account is for the app, not for fm.

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:account", "name": "agent", "password": "hunter2hunter2", "privilegeSet": "[Data Entry Only]"}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:account"}
```

### Grant an extended privilege

Verified: **on disk** · regression-tests quirk 2, 61

> A blank file has only `fmapp` granted. The connector needs `fmplugin`, fmp-URL script starts need `fmurlscript`, and OData/Data API need `fmodata`/`fmrest` -- plus the SERVER engine switch, which lives outside the file entirely (quirks 2, 57). Grants take effect live on a hosted file, no reopen (quirk 61).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "update:extendedPrivilege", "name": "fmplugin", "privilegeSets": ["[Full Access]"]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:extendedPrivilege"}
```

## table

### Rename a table

Verified: **on disk** · regression-tests quirk 41

> The same-named occurrence is renamed with it and dependent calc TEXT is rewritten by FileMaker, because references are held by id. Diff the id graph, not the calc text, across a rename (quirk 41).

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "update:table", "name": "B", "newName": "B2"}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:table"}
{"op": "read:tableOccurrence"}
```

## theme

### Derive a custom theme from the file's own and regroup it

Verified: **on disk** · regression-tests quirk 16 (lifted in 0.7.0, see quirk 100)

> Every theme this catalog makes is DERIVED -- omitting `base` copies whatever the file already wears, and a name matching a FileMaker Pro built-in installs that built-in first. `css` REPLACES a theme's styles wholesale in ADT's own small CSS-like vocabulary, never a merge -- read `fm-cli help theme-css` before writing any. This boundary held through 0.6.0 (quirk 16); 0.7.0 lifts it -- see quirk 100.

```json
{"op": "create:theme", "displayName": "Suite Theme"}
{"op": "update:theme", "name": "Suite Theme", "group": "suite"}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:theme", "name": "Suite Theme", "detail": true}
```

## valueList

### Create a value list

Verified: **on disk**

Needs this schema in place first — run it as its OWN `fm` invocation, not prepended to the ops below (a table or occurrence made in the same batch is not always usable yet):

```json
{"op": "create:table", "name": "A"}
{"op": "create:field", "table": "A", "name": "Name", "type": "text"}
{"op": "create:field", "table": "A", "name": "Id", "type": "text"}
{"op": "create:table", "name": "B"}
{"op": "create:field", "table": "B", "name": "AId", "type": "text"}
{"op": "create:field", "table": "B", "name": "Amount", "type": "number"}
```

```json
{"op": "create:valueList", "name": "Status", "type": "custom", "values": ["Open", "Closed"]}
```

Confirm it landed (run in a fresh process):

```json
{"op": "read:valueList", "name": "Status", "detail": true}
```
