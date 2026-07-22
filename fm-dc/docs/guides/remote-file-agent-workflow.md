# Working a Remote FileMaker File with the Agentic Toolkit

**Status:** proven working (2026-07-15, FMS 26.0.1 Linux, FM Pro 2026 macOS)
**Proven against:** `AI_RC_SP_24_Lite.fmp12` on `agentic-workshop.atrcc.com`
**Companion design notes:** `fm-dc/docs/design-notes/filemaker-xml-export-patching-harness.md`

This guide sets up a hosted FileMaker file so an agent can read its full structure on
demand — no download, no file close, no human in the runtime loop. One paste to install;
after that the agent exports, ingests, and parses by itself.

---

## 1. The loop

```
agent ──POST /fmi/odata/v4/{db}/Script.Agent_SaXML_Export──▶ FMS runs script server-side
                                                              │  Save a Copy as XML
                                                              │  (catalog-selected, → temp)
                                                              │  Insert from URL → $xmlBlob
                                                              │  Set Field: text + container
agent ◀──scriptResult JSON {error, recordId, runId, path}─────┘
agent ──GET /{db}/{LogTable}({recordId})?$select={TextField}──▶ XML comes back as JSON text
agent: save → schema/ddrs/YYYY-MM-DD/ → parse → refresh knowledge base → hash → ledger
```

Measured: 11 MB ScriptCatalog export in ~10s server-side + ~6s transport.

### Session lifecycle (the working doctrine)

- **Session open, unknown file** → run the export. That's the baseline map.
- **During the session** → clipboard round-trips (paste-in script XML, copy-out results).
  Fast, surgical, human-gated.
- **Session close** → export again. Diff against the baseline = the *derived* changelog —
  what actually changed, not what anyone believes changed.

Export brackets the session; clipboard fills it.

---

## 2. Prerequisites

| Requirement | Why |
|---|---|
| FileMaker Server 2026 (26.0.1+) with OData enabled | trigger + transport + schema mutations |
| An account with the `fmodata` extended privilege | all OData calls |
| That account can run scripts in the file | the trigger (`Script.{name}` 404s if not) |
| FileMaker Pro 2026 (any machine) — **install time only** | one paste into Script Workspace |
| Credentials in a `hostedFile.md` (never committed) | `server - host` / `file - X.fmp12` / `account - user` / `pass - secret` (note the ` - ` separator) |

The runtime path needs no Pro, no plugins, no ProofKit — pure OData.

---

## 3. One-time file setup — the setup interview

> **Since v0.7.0 this interview is the FALLBACK, not the default.** The standard
> install is the v5 paste-in pair — `templates/saxml-table.xml` +
> `templates/agent-saxml-export-v5.xml`, table → layout → script, no placeholders,
> fixed names `SAXML`/`ResponseText` (walkthrough: the scaffold's `workflow/02`
> runbook). Run this interview only when the standard `SAXML` table can't land
> as-is (naming conventions, reuse of an existing log table, no-new-tables rule).

Every file is different: some already have a usable log table, some need one created,
and the layout situation varies. So setup is an **agent-led interview**, not a fixed
recipe — and nothing gets hardcoded. When a project first points at a hosted file (or
the user says "set up the export"), the agent walks these steps, asking before acting:

**Step 0 — Offer.** "This file doesn't have the export capability yet — want to set it
up now?" (Skip everything below if the trigger already answers: a `POST Script.Agent_SaXML_Export`
probe that doesn't 404 means it's already installed.)

**Step 1 — Discover and choose the drop table.** List the file's tables over OData and
look for an existing candidate: a regular table (NOT globals — server sessions discard
them) that is **already on a layout**, with room for text fields. Present the options:

- *Reuse table X* — least invasive; the agent adds any missing fields via OData
- *Create a new table* (e.g. `AgentLog`) — cleanest separation; needs the layout step

Required fields either way: a **text field** for the XML payload (the transport — SaXML
output is UTF-8 text), a text label field, a text params field (audit trail), and
optionally a **container field** (bonus copy; see §6 gotcha 5).

**Step 2 — Create/extend the table (agent, via OData).** New table: `POST /FileMaker_Tables`
with SQL DDL types. Adding fields to an existing table:

```
PATCH /fmi/odata/v4/{db}/FileMaker_Tables/{table}
{"fields": [{"name": "XMLText", "type": "VARCHAR(255)"}]}     ← PATCH, not POST
```

Expect and retry on error 303 (a Pro client sitting in Manage Database blocks all
schema changes).

**Step 3 — Layout (human, only if a new table was created).** No API can create
layouts. Ask the operator to make one layout in Pro showing the new table (name it
after the table), then confirm. Skipped entirely when reusing a table that's already
on a layout.

**Step 4 — Generate the script.** From the plugin template
`${CLAUDE_PLUGIN_ROOT}/templates/agent-saxml-export.template.xml`, substitute the
placeholders with THIS file's names: `{{DROP_LAYOUT}}`, `{{DROP_TO}}`, `{{LABEL_FIELD}}`,
`{{PARAMS_FIELD}}`, `{{TEXT_FIELD}}`, `{{CONTAINER_FIELD}}` (delete that one Set Field
step if the table has no container). Print the result **on screen** — never silently to
the clipboard; the operator must be able to see and version-check what they're pasting.
The first step is a Comment carrying the version and date.

**Step 5 — Install (human pastes, once).** In FileMaker Pro, on the hosted file:

1. Script Workspace → New Script → name it exactly **`Agent_SaXML_Export`**
2. Click into the empty step area → paste → the steps appear
3. Verify: every `Set Variable` shows its variable name (`$param`, `$runId`, `$options`,
   `$fmPath`, `$xmlBlob`, …) — a blank name means the paste silently dropped it
4. Check **"Run script with full access privileges"** (Save a Copy as XML requires it)
5. Save (⌘S) — *unsaved scripts run the old version; this bites*

**Step 6 — Record and verify.** Write the chosen names into the project config
(`fm/fm-dc.json`, under the file entry: `dropLayout`, `dropTO`, `textField`, …) so the
export driver and every later session read them from config — never hardcoded. Then
copy the script back out of FileMaker for a round-trip check (version comment present,
names resolved to real IDs), and fire a one-catalog smoke export: success = `error: 0`
AND `chars > 0` AND fetched bytes > 0.

---

## 4. The script — `Agent_SaXML_Export` v3

Contract:

- **Parameter** (JSON text): `{"runId": "...", "options": {"catalogs_included": ["ScriptCatalog", ...], "include_details": false, "split_catalogs": false, "standalone_binarydata": false}}`
- **Result** (JSON text): `{"error": N, "stage": "export"|"done", "runId", "path", "recordId", "chars"}`
  — `error ≠ 0` or a later `chars`/byte count of 0 means failure regardless of what any tool banner says.
- Rules baked in: catalog **selection on, splitting off, DDR_INFO off** (one small file);
  errors captured per hop; the result carries the record ID for pickup.

**Never adapt by hand — generate from the template** (`templates/agent-saxml-export.template.xml`,
v4, which also fixes the `chars` context bug below) via the §3 interview. The template's
placeholders cover the layout, table occurrence, and field names; ids are `id="1"`
placeholders — FileMaker resolves by exact name on paste (case- and whitespace-sensitive)
and stamps real IDs.

Historical reference — the v3 XML exactly as first proven (targets `AI_RequestLog` /
`Prompt` / `PayLoadJSON` / `XMLDrop` / `ResponseText`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<fmxmlsnippet type="FMObjectList">
  <Step enable="True" id="89" name="Comment">
    <Text>Agent_SaXML_Export v3 (2026-07-15) - triggered via OData Script.Agent_SaXML_Export. Param: {runId, options:{catalogs_included,...}}. Exports catalog-selected SaXML to temp, loads XMLDrop (container) + ResponseText (text transport), returns JSON result incl. chars. v3: added ResponseText text-field transport because OData $value 502s on this server.</Text>
  </Step>
  <Step enable="True" id="86" name="Set Error Capture">
    <Set state="True"/>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[Get ( ScriptParameter )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$param</Name>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[Let ( r = JSONGetElement ( $param ; "runId" ) ; If ( IsEmpty ( r ) ; Get ( UUID ) ; r ) )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$runId</Name>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[JSONGetElement ( $param ; "options" )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$options</Name>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[Get ( TemporaryPath ) & "saxml_" & $runId & ".xml"]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$fmPath</Name>
  </Step>
  <Step enable="True" id="3" name="Save a Copy as XML">
    <Option state="False"/>
    <OutputEntireBinaryData state="False"/>
    <SpecifyJSONOptions state="True"/>
    <UniversalPathList>$fmPath</UniversalPathList>
    <SaXML>
      <JSONOptions>
        <Calculation><![CDATA[$options]]></Calculation>
      </JSONOptions>
    </SaXML>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[Get ( LastError )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$exportErr</Name>
  </Step>
  <Step enable="True" id="68" name="If">
    <Restore state="False"/>
    <Calculation><![CDATA[$exportErr <> 0]]></Calculation>
  </Step>
  <Step enable="True" id="103" name="Exit Script">
    <Calculation><![CDATA[JSONSetElement ( "{}" ; [ "error" ; $exportErr ; JSONNumber ] ; [ "stage" ; "export" ; JSONString ] ; [ "runId" ; $runId ; JSONString ] ; [ "path" ; $fmPath ; JSONString ] )]]></Calculation>
  </Step>
  <Step enable="True" id="70" name="End If"/>
  <Step enable="True" id="6" name="Go to Layout">
    <LayoutDestination value="SelectedLayout"/>
    <Layout id="1" name="AI_RequestLog"/>
  </Step>
  <Step enable="True" id="7" name="New Record/Request"/>
  <Step enable="True" id="76" name="Set Field">
    <Calculation><![CDATA["Agent SaXML export " & $runId]]></Calculation>
    <Field table="AI_RequestLog" id="1" name="Prompt"/>
  </Step>
  <Step enable="True" id="76" name="Set Field">
    <Calculation><![CDATA[$param]]></Calculation>
    <Field table="AI_RequestLog" id="1" name="PayLoadJSON"/>
  </Step>
  <Step enable="True" id="160" name="Insert from URL">
    <NoInteract state="True"/>
    <DontEncodeURL state="False"/>
    <SelectAll state="True"/>
    <VerifySSLCertificates state="False"/>
    <Calculation><![CDATA[ConvertFromFileMakerPath ( $fmPath ; URLPath )]]></Calculation>
    <Text/>
    <Field>$xmlBlob</Field>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[Get ( LastError )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$insertErr</Name>
  </Step>
  <Step enable="True" id="76" name="Set Field">
    <Calculation><![CDATA[$xmlBlob]]></Calculation>
    <Field table="AI_RequestLog" id="1" name="XMLDrop"/>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[If ( $insertErr <> 0 ; $insertErr ; Get ( LastError ) )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$insertErr</Name>
  </Step>
  <Step enable="True" id="76" name="Set Field">
    <Calculation><![CDATA[Let ( t = TextDecode ( $xmlBlob ; "utf-8" ) ; If ( IsEmpty ( t ) ; $xmlBlob ; t ) )]]></Calculation>
    <Field table="AI_RequestLog" id="1" name="ResponseText"/>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[If ( $insertErr <> 0 ; $insertErr ; Get ( LastError ) )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$insertErr</Name>
  </Step>
  <Step enable="True" id="141" name="Set Variable">
    <Value>
      <Calculation><![CDATA[Get ( RecordID )]]></Calculation>
    </Value>
    <Repetition>
      <Calculation><![CDATA[1]]></Calculation>
    </Repetition>
    <Name>$recId</Name>
  </Step>
  <Step enable="True" id="75" name="Commit Records/Requests">
    <NoInteract state="True"/>
    <Option state="False"/>
    <ESSForceCommit state="False"/>
  </Step>
  <Step enable="True" id="6" name="Go to Layout">
    <LayoutDestination value="OriginalLayout"/>
  </Step>
  <Step enable="True" id="103" name="Exit Script">
    <Calculation><![CDATA[JSONSetElement ( "{}" ; [ "error" ; $insertErr ; JSONNumber ] ; [ "stage" ; "done" ; JSONString ] ; [ "runId" ; $runId ; JSONString ] ; [ "path" ; $fmPath ; JSONString ] ; [ "recordId" ; $recId ; JSONNumber ] ; [ "chars" ; Length ( AI_RequestLog::ResponseText ) ; JSONNumber ] )]]></Calculation>
  </Step>
</fmxmlsnippet>
```

Known v3 defect (harmless, fix in v4): `chars` evaluates after `Go to Layout [original]`,
so it reads 0 — wrong record context. Trust the fetched byte count, not `chars`, until v4
moves the `Length()` before the layout switch.

---

## 5. Running an export

Trigger (any HTTP client; `export_run.py` wraps all of this):

```
POST https://{host}/fmi/odata/v4/{db}/Script.Agent_SaXML_Export
Authorization: Basic {account:pass}
{"scriptParameterValue": "{\"runId\":\"run-...\",\"options\":{\"catalogs_included\":[\"ScriptCatalog\"],\"include_details\":false,\"split_catalogs\":false}}"}
```

Pickup — table and field come from the project config recorded in §3 step 6, never
hardcoded (shown here with the proven file's names):

```
GET https://{host}/fmi/odata/v4/{db}/{dropTO}({recordId})?$select={textField}
e.g. .../AI_RequestLog(9)?$select=ResponseText
```

Then, in the project:

1. Save to `schema/ddrs/YYYY-MM-DD/` (one file — selection on, splitting off)
2. Parse with the project's fm-saxml pipeline (auto-detects single-file vs split):
   `splitter.py` → `schema/parsed/` → `readable.py` → `schema/readable/{db}/`
3. Record: timestamp, catalogs, byte count, **sha256 of the normalized XML** → the ledger
4. Diff against the previous export — notes derive from the diff, never from intent

Catalog names (FM 26): `PersistentStoreCatalog, BaseDirectoryCatalog, FileAccessCatalog,
ExternalDataSourceCatalog, BaseTableCatalog, TableOccurrenceCatalog,
CustomFunctionsCatalog, ValueListCatalog, FieldCatalog, RelationshipCatalog,
CustomMenuCatalog, CustomMenuSetCatalog, ScriptCatalog, ThemeCatalog, LayoutCatalog,
LibraryCatalog, PrivilegeSetsCatalog, ExtendedPrivilegesCatalog, AccountsCatalog, Metadata`.
Pull only what the change type needs — `ScriptCatalog` after script work, `FieldCatalog` +
`BaseTableCatalog` after schema work. Layouts are enormous; include only when needed.

---

## 6. Gotchas — every one of these cost us a debugging pass

1. **Error 303 "schema is locked"** on OData schema calls → a Pro client is sitting in
   Manage Database. Retry after it closes. Expect this constantly in shared files.
2. **`Script.{name}` 404s right after the script is saved** → server metadata lag.
   Retry after ~30s. Also 404s if the account can't see the script.
3. **Unsaved script = old version runs.** The single most common "why didn't my change
   take" answer. Save (⌘S) before triggering.
4. **`Insert from URL` into a *field* target returns error 102** unless the field is on
   the current layout — only **variable** targets are layout-exempt (`Set Field` is also
   exempt). Portable pattern: `Insert from URL → $var`, then `Set Field [field ; $var]`.
5. **OData containers:** JSON representations are ALWAYS `null` (even when populated) —
   binary is `$value`-only, and on FMS 26.0.1/Linux `$value` 502s at nginx. Don't fight
   it: SaXML output is UTF-8 text — **transport through a text field** via ordinary JSON.
6. **`ConvertFromFileMakerPath ( path ; URLPath )` already returns `file:///...`** —
   prefixing `"file://"` yields `file://file:///...` and fails. (This bug is in older
   design notes; the validator caught it.)
7. **Add fields via OData with `PATCH`**, not POST (POST → `-1012 syntax error`).
8. **OData create-table wants SQL DDL types** (`VARCHAR(255)`, `NUMERIC`, `BLOB`), not
   FileMaker type names (`8310` otherwise).
9. **Paste-handler silent drops:** emit FileMaker's exact native step XML (Kear spec,
   `fm-xml` skill). Verify Set Variable names survived every paste.
10. **The tools lie** (design notes §7): "Patch File Applied", `error 0` with an empty
    payload, `"Nodes succeeded: 0"` on success. Layer checks: script-level error JSON →
    byte count > 0 → parse the XML → normalized hash vs. previous.

---

## 7. Division of labor (which tool for which job)

| Job | Tool |
|---|---|
| Read structure (baseline / verification map) | this export loop (OData-triggered SaXML) |
| Schema mutations (tables, fields) | OData (`fm-odata` skill) — the only live path |
| Layouts | Pro, by hand — no API can make them |
| Scripts in/out during a session | clipboard round-trip (`fm-xml` / `fm-scripts` skills) |
| Data CRUD | Data API / ProofKit orchestrator |
| Verification on open files | ProofKit MCP (SQL, metadata) |
| Patching a closed local copy | `fm-patch` pipeline (separate; see that skill) |

---

## 8. Provenance

Proven live 2026-07-15 against `AI_RC_SP_24_Lite.fmp12`, FMS 26.0.1 (Linux) at
`agentic-workshop.atrcc.com`, FM Pro 2026 (macOS) + ProofKit MCP 3.0.3 for the paste lane:
run `run-20260715-100118` exported an 11,136,794-byte ScriptCatalog (10.6s server, 5.8s
transport), sha256 `da6f3d57f186fe40…`, self-referentially containing `Agent_SaXML_Export`.
Raw findings log: `fm-dc/sandbox/hosted-harness/FINDINGS.md` (local sandbox, not shipped).
