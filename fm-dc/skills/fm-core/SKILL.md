---
name: fm-core
description: >
  FileMaker Pro development — calculations, scripts, schema design, and integration patterns.
  Use this skill whenever the user mentions FileMaker, FM, FMP, .fmp12 files, FileMaker calculations,
  FileMaker scripts, ExecuteSQL, fmxmlsnippet, MBS Plugin, Claris, FileMaker Server, FileMaker 2024,
  FileMaker 2025, FileMaker 2026, Generate Response from Model, Insert Image Caption, persistent data
  store, or any FileMaker-related development task. Also trigger when the user
  is working with XML script snippets, clipboard round-trips, DDR exports, OData APIs for FileMaker,
  or migrating FileMaker solutions to web stacks. Even if the user doesn't say "FileMaker" explicitly,
  trigger if the context involves FM-specific functions (Let, Case, GetField, ExecuteSQL, JSONGetElement,
  TextStyleAdd, PSOS, Set Variable, etc.).
---

# FileMaker Development Skill

Comprehensive reference for FileMaker Pro development including calculations, scripting, schema patterns, XML snippet generation, and AI integration.

## Quick Reference

For detailed patterns and examples, see the reference files:
- `references/calc-patterns.md` — Calculation syntax, JSON handling, text formatting, ExecuteSQL
- `references/script-patterns.md` — Script step patterns, error handling, PSOS, AI steps

For **paste-ready XML generation** (scripts, custom functions, layout objects, field definitions), use the vendored Kear skills — they carry the round-trip-verified specs and silent-failure rules:
- `filemaker-xml` — script + custom-function `fmxmlsnippet` (220+ step IDs, FM 2026 steps)
- `filemaker-layout-xml` — layout object XML (`LayoutObjectList`)
- `filemaker-field-xml` — field definition XML for Manage Database
- Validate any snippet before pasting: `python3 ${CLAUDE_PLUGIN_ROOT}/tools/fmlint/validate_snippet.py <file>`

## First-Party Docs on Demand

Claris publishes its entire help corpus as agent-friendly Markdown. When unsure about a script step, function, or option — especially anything FM 2025/2026 — **fetch the authoritative page instead of answering from memory**:

```bash
curl -sL https://help.claris.com/markdown/en/pro-help/{topic}.md   # -sL required: every URL 302s once
```

- Index of all pages: `https://help.claris.com/llms-full.txt` — don't guess slugs; Markdown slugs don't always match HTML ones
- Other doc sets swap the path segment: `server-help`, `data-api-guide`, `odata-guide`, `sql-reference`, `claris-mcp-help`, `security-guide`, …
- A valid page starts with YAML frontmatter (`---`); a body starting `<!DOCTYPE` means a bad slug (302 to the 404 page)
- Frontmatter `version`/`version_year` can lag the content — FM 2026 release notes shipped while frontmatter still said `version: 22`
- What changed per version: `https://help.claris.com/markdown/en/pro-release-notes/index.md`
- Full corpus reference + curated AI page list: `resources/claris-markdown-docs-reference.md` in this project

### Version naming map

| Marketing name | Internal version |
|---|---|
| FileMaker 2023 | 20 |
| FileMaker 2024 | 21 (AI steps originated here) |
| FileMaker 2025 | 22 |
| FileMaker 2026 | 26 — number jumped to match the year |

---

## FileMaker Calculation Fundamentals

### Syntax Rules
- Line separator: `¶` (pilcrow) for carriage returns in text, `&` for concatenation
- String delimiter: double quotes `"` — escape with `\"` inside strings
- Comparison operators: `=`, `<>` (not equal), `<`, `>`, `≤`, `≥`
  - **IMPORTANT**: Use `<>` not `≠` in calculations — `≠` causes issues in some contexts
- Boolean: `True` / `False` or `1` / `0`
- Comments in calcs: `/* comment */` or `// comment`
- Null/empty: `""` (empty string) — FileMaker has no null concept; empty string is the closest
- Field references: `TableOccurrenceName::FieldName`

### Core Functions

**Let / Let with multiple variables:**
```
Let ( [
  _var1 = "value" ;
  _var2 = SomeField ;
  _var3 = _var1 & " " & _var2
] ;
  // expression using variables
  _var3
)
```
- Local variable prefix `_` is convention for Let variables
- `$var` = script-scoped variable
- `$$var` = file-scoped global variable

**Case:**
```
Case (
  condition1 ; result1 ;
  condition2 ; result2 ;
  defaultResult
)
```

**If (calc function, not script step):**
```
If ( condition ; trueResult ; falseResult )
```

### JSON Functions (FM 16+)
```
JSONSetElement ( json ; keyOrPath ; value ; type )
JSONGetElement ( json ; keyOrPath )
JSONListValues ( json ; keyOrPath )           // returns value-per-line from array
JSONListKeys ( json ; keyOrPath )
JSONFormatElements ( json )                   // pretty-print; returns "?" on invalid JSON
JSONDeleteElement ( json ; keyOrPath )
```

JSON types for JSONSetElement:
- `JSONString` (1), `JSONNumber` (2), `JSONObject` (3), `JSONArray` (4), `JSONBoolean` (5), `JSONNull` (6), `JSONRaw` (0)

**Nested access:** `JSONGetElement ( $json ; "ratings.overall" )`

**Validating JSON:**
```
Left ( JSONFormatElements ( $json ) ; 1 ) <> "?"
```

### Text Styling
```
TextStyleAdd ( text ; Bold )
TextStyleAdd ( text ; Italic )
TextStyleAdd ( text ; Bold + Italic )
TextStyleAdd ( text ; Underline )
TextStyleRemove ( text ; AllStyles )
TextColor ( text ; RGB ( r ; g ; b ) )
TextSize ( text ; pointSize )
```
- Styling only renders in text fields on layouts or in merge fields
- Calculation fields with text result type can display styled text

### ExecuteSQL
```
ExecuteSQL ( "SELECT field FROM TableOccurrenceName WHERE id = ?" ; fieldSep ; rowSep ; arg1 ; arg2 )
```
- **Uses table occurrence (TO) names** — not base table names. If the base table is `DataAPI` but the TO is `zDataAPI`, you must use `FROM zDataAPI`. Using the base table name returns `?`.
- Field separator and row separator are typically `""` (tab) and `""` (return), or custom
- Use `?` placeholders for parameters — prevents SQL injection and handles quoting
- Returns `?` on error — always check: `Left ( $result ; 1 ) <> "?"`
- **Does not support** INSERT, UPDATE, DELETE — read-only
- Date format in SQL: `DATE '2026-04-13'`

### Date Formatting for APIs
When sending dates to AI models or APIs, format explicitly:
```
Year ( Get ( CurrentDate ) ) & "-" &
Right ( "0" & Month ( Get ( CurrentDate ) ) ; 2 ) & "-" &
Right ( "0" & Day ( Get ( CurrentDate ) ) ; 2 )
```
This ensures YYYY-MM-DD regardless of the user's system date format.

---

## FileMaker Scripting Essentials

### Standard Script Structure
Every script should follow this pattern:
1. `# (comment)` — Script purpose
2. `Set Error Capture [On]`
3. `Allow User Abort [Off]`
4. Parameter parsing (if applicable)
5. Validation / early exits
6. Main logic
7. Error handling
8. Commit Records
9. Exit Script with result

### Error Handling Pattern
```
Set Error Capture [On]
# ... do something ...
Set Variable [$error ; Get ( LastError )]
If [$error <> 0]
  # Handle error — log, show dialog, or exit
  Exit Script [0]
End If
```

### Variable Scoping
- `$var` — Local to current script execution
- `$$var` — Global, persists until file closes or explicitly cleared
- **Convention**: Prefix with purpose: `$apiKey`, `$qaText`, `$response`

### Perform Script on Server (PSOS)
- Runs script on FileMaker Server — no layout context, no dialogs
- Cannot access global variables from the client
- Pass data via script parameter, return via Exit Script [result]
- **Common gotcha**: Script steps that require layout context (Insert Text, Go to Field, etc.) fail silently on server

### Insert Text vs Set Variable
- `Insert Text` inserts literal text into a field or variable — great for long multi-line text (like AI instructions) because you avoid CDATA/concatenation complexity. Line breaks are `&#13;` in the XML.
- `Set Variable` evaluates a calculation — use for dynamic values, field references, function calls
- **Insert Text requires layout context** for fields (not for variables) — won't work via PSOS when targeting a field
- **Rule of thumb**: Use Insert Text for long literal strings (instructions, templates). Use Set Variable for everything else.

### AI Script Steps (FM 2024+)

**Configure AI Account:**
```
Configure AI Account [Account Name: "name" ; API Key: $apiKey ; Model Provider: ChatGPT]
```
- Model Provider options (docs call it "Model Provider"; older snippets say "Model Type"): **ChatGPT** (OpenAI), **Anthropic** (Claude — native in FM 22), **Gemini** (Google — native in FM 26), **Custom** (any OpenAI-compatible endpoint, requires Endpoint URL ending with `/`)
- Claris AI Model Server = **Custom** provider with the endpoint from Admin Console (e.g. `"https://myserver.example.com/llm/v1/"`)
- Account name is a label you define — used to reference in Generate Response
- Account is per-file, per-session — cleared when the file closes
- Model name strings: `gpt-4o` / `gpt-4o-mini` for ChatGPT; `claude-sonnet-4-5` / `claude-opus-4` etc. for Anthropic; check Claris tech specs for currently recommended models per provider

**Generate Response from Model:**
```
Generate Response from Model [
  Account Name: "name" ;
  Model: $model ;
  User Prompt: $prompt ;
  Instructions: $instructions ;
  Response: $response
]
```
- `Instructions` = system prompt (persistent context/persona)
- `User Prompt` = the actual request with variable data
- Response goes into a variable or field
- Inject dynamic context (dates, IDs, user info) into the User Prompt, not Instructions
- Check `Get ( LastError )` immediately after — network/API failures are common
- Stream option: On = incremental delivery, Off = wait for complete response

**Best practice for AI prompts returning JSON:**
- Instructions: Define the persona, output format, and rules
- User Prompt: Include the data + `"Today's date is " & <formatted date>`
- Always include: "Return ONLY the JSON object. No markdown, no commentary, no code fences."
- Validate response with `Left ( JSONFormatElements ( $response ) ; 1 ) <> "?"`

### FM 2026 AI Additions

- **Insert Image Caption** / **Insert Image Captions in Found Set** — send container images to an image-captioning model, caption into field/variable. **Claris AI Model Server only** (Custom provider account).
- **Generate Response from Model** gains **Include tool calls and tool results** — richer saved message history for agentic flows. (Also fixed in 26: with Stream off, the message-history variable now populates.)
- **Parameters option** on Insert Embedding / Insert Embedding in Found Set / Perform Semantic Find — pass provider-specific params like `dimension`. `CURLOPT_TIMEOUT` key sets a max request time (seconds) on Generate Response, NL query steps, and Perform RAG Action.
- **Perform RAG Action** now returns the document ID on add (store it for later removal), accepts per-request Similarity Threshold / Top-N, and has a **Tokens per Text Chunk** option.
- **Field annotations** — per-field AI description set in Advanced Options for Field ("Add annotation in DDL"); sent to models by Perform SQL Query / Find by Natural Language without touching field comments. Read via new `FieldAnnotation()`; `GetFieldsOnLayout()` includes them.
- Cohere image embeddings supported on the embedding steps and `GetEmbedding()`.

### FM 2026 Non-AI Highlights

- **Persistent data store** — named values saved in the schema (not records): app version, JS libraries for web viewers, fixed AI prompts, add-on config. `Configure Persistent Data` script step + `GetPersistentData()` / `ListPersistentDataIDs()`.
- **PDF script step suite** — Create / Open / Append / Close / Cancel / Print PDF compose multi-source PDFs in memory; Save Records as PDF gains **Save to** (path, container, variable, or append to open PDF).
- **Window UUID** — Select/Close/Move-Resize/Set Window Title can target by UUID; `Get(WindowUUID)` returns the active window's.
- **FileMaker SQL** now supports `FOREIGN KEY` in `CREATE TABLE` / `ALTER TABLE`, and quoted `"ROWID"` / `"ROWMODID"` (also available as named constants in calcs). `ExecuteSQL()` remains read-only.
- **Insert from URL**: `application/json` responses stored in a variable are auto-parsed and cached — faster subsequent JSON ops. New `--proxy-negotiate` / `--proxy-ntlm` options.
- **Save a Copy as XML** overhaul: UTF-8 (was UTF-16 LE), multi-file batch with Summary.xml, per-catalog file splitting, options as JSON, and a script-step equivalent. (Still a different format from the DDR export — the `schema/` splitter pipeline wants the DDR.)
- `Export Field Contents` now works from FileMaker Server, Data API, and OData scripts.
- New functions: `FieldAnnotation`, `BaseTableComment`, `FieldDisplayNames`, `GetPersistentData`, `ListPersistentDataIDs`, `Get(WindowUUID)`, `Get(AccountPasswordDaysRemaining)`, `Get(GuidedAccessState)`.

---

## Common Patterns

### Display Calc for JSON Data
When a field stores raw JSON and you need a human-readable display:
```
Let ( [
  _json = Table::JsonField ;
  _valid = not IsEmpty ( _json ) and Left ( JSONFormatElements ( _json ) ; 1 ) <> "?"
] ;
  Case ( not _valid ; "" ;
    Let ( [
      _val1 = JSONGetElement ( _json ; "key1" ) ;
      _val2 = JSONGetElement ( _json ; "key2" )
    ] ;
      TextStyleAdd ( "Label" ; Bold ) & "¶" &
      _val1 & "¶¶" &
      TextStyleAdd ( "Label 2" ; Bold ) & "¶" &
      _val2
    )
  )
)
```

### Bullet List from JSON Array
```
Let ( [
  _items = JSONListValues ( _json ; "arrayKey" )
] ;
  Case ( IsEmpty ( _items ) ;
    TextStyleAdd ( "None" ; Italic ) ;
    "• " & Substitute ( _items ; "¶" ; "¶• " )
  )
)
```

### API Key Retrieval Pattern
Store API keys in a config/settings table, retrieve via ExecuteSQL:
```
Set Variable [$apiKey ;
  Trim ( ExecuteSQL ( "SELECT APIKey_AI FROM zDataAPI WHERE DataAPIID = ?" ; "" ; "" ; 1 ) )
]
If [IsEmpty ( $apiKey )]
  Exit Script [0]
End If
```

### Collect Related Data for AI Processing
```
Set Variable [$qaText ; List ( RelatedTable::TextField )]
If [IsEmpty ( $qaText )]
  Exit Script [0]
End If
```
`List()` across a relationship returns all related values, one per line. Preferred over ExecuteSQL for simple collection from a relationship — no SQL syntax, respects sort order on the relationship.

---

## Schema & Naming Conventions

### Table Naming
- Utility/system tables: prefix with `z` (e.g., `zFormSubmission`, `zDataAPI`)
- Junction tables: `TableA_TableB`
- Keep table occurrence names meaningful on the relationship graph

### Field Naming
- PrimaryKey: `TableNameID` (e.g., `FormSubmissionID`)
- ForeignKey: matching name from parent table (e.g., `ClientID`)
- Timestamps: `CreationTimestamp`, `ModificationTimestamp`
- Audit: `CreatedBy`, `ModifiedBy`
- Calculated/display fields: descriptive name (e.g., `AI_Summary`, `QA_Display`, `Name_First_Last`)

---

## MBS Plugin & Claude Code Integration

### Clipboard Round-Trip Workflow
The MBS Plugin enables copying FileMaker scripts and layout objects as XML, editing them externally (e.g., with Claude Code), and pasting them back.

1. In FileMaker: Select script steps → Copy
2. MBS reads clipboard as fmxmlsnippet XML
3. Edit XML externally (Claude Code can parse/generate this format)
4. MBS writes modified XML back to clipboard
5. In FileMaker: Paste script steps

See the `filemaker-xml` skill for the fmxmlsnippet XML format, step IDs, and worked examples; validate with `${CLAUDE_PLUGIN_ROOT}/tools/fmlint/validate_snippet.py` before pasting.

### DDR-Based Context Export
Export the Database Design Report (DDR) as XML to give Claude Code full schema context:
- Tables, fields, relationships, value lists
- Scripts with all steps
- Layout objects and their positions

---

## Migration: FileMaker to Web Stack

When migrating FileMaker solutions to modern web stacks:
- **Target stack**: Supabase (PostgreSQL + Auth + Storage) + Vercel (Next.js)
- **Approach**: Feature-by-feature migration, not big-bang
- **Data layer**: Map FM tables → Postgres tables, FM relationships → foreign keys + RLS policies
- **Business logic**: FM scripts → Edge Functions or API routes
- **UI**: FM layouts → React components
- **Auth**: FM privilege sets → Supabase Auth + RLS

---

## Gotchas & Tips

1. **Get ( CurrentDate ) format varies by system** — always format explicitly for APIs
2. **JSONGetElement returns empty string for missing keys** — not an error, not "null"
3. **ExecuteSQL uses table occurrence names** — not base table names. `FROM DataAPI` fails if the TO is `zDataAPI`.
4. **Insert Text requires layout context for fields** — use Set Variable instead for portability, especially via PSOS. But Insert Text works fine targeting `$variables` without layout context.
5. **PSOS has no UI access** — no dialogs, no layout-dependent steps
6. **Commit Records after Set Field** — changes aren't saved until committed
7. **List() on empty relationship returns empty** — safe to use without null checking
8. **TextStyleAdd only visible in text fields** — number/date result types ignore styling
9. **FileMaker "null" is empty string** — when building JSON, use JSONNull type explicitly
10. **The `≠` operator** — works in most contexts but can cause issues; prefer `<>`
11. **FM cURL options use `¶` (pilcrow) as line separator** — `\n` produces literal backslash-n, not a line break. Use `& ¶ &` between options.
12. **cURL header values need `Quote()`** — e.g., `"--header " & Quote ( "Authorization: Bearer " & $token )` to handle special characters.
13. **Tokens/secrets used in cURL headers cannot start with `-`** — cURL parses a leading dash as a new option flag. Use hex tokens or regenerate until the first character is alphanumeric.
14. **Configure AI Account misspells "Account"** — the XML schema uses `<AccoutName>` and `<SetLLMAccout>`. This is not a typo in your code — it's in FileMaker's actual XML format.
