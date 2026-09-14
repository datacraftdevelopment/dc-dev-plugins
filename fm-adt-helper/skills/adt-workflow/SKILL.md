---
name: adt-workflow
description: >
  The top-level map for working with Claris's Agentic Development Toolkit (ADT) on
  FileMaker files. Use at the start of ANY FileMaker task on an ADT-equipped machine —
  schema changes, scripts, layouts, data reads/writes, web viewer apps — to pick the
  right lane before touching anything. Also use when deciding between the fm CLI, the
  adt CLI, and the MCP data tools; when the MCP tools time out or the handshake is in
  question; when choosing between the ADT Helper plug-in and MBS/BaseElements for an
  in-FileMaker capability; or when someone asks "what is ADT", "which lane", "do I need
  the connector", or "CLI vs MCP".
---

# ADT workflow — the map and the lanes

The **Agentic Development Toolkit** (ADT, 0.4.0) is Claris's official agentic
FileMaker stack. Four pieces:

| Piece | What it is |
|---|---|
| **Claude Code plugin** | `claris/filemaker-agentic-development` — carries the skills, the `adt` binary, and the `adt-mcp` server |
| **`fm` CLI** | `~/.local/bin/fm` — the schema/script/layout engine. Links the *real* FileMaker engine and opens the `.fmp12` itself; no FileMaker Pro involved |
| **`adt` CLI** | Project orchestration (init/connect/components/app/layout/typegen/deploy/doctor). Lives inside the plugin, deliberately **not on PATH** |
| **`adt-mcp` bridge** | 7 MCP tools that reach FileMaker Pro through the `ADT.fmplugin` HTTP service on **port 1366** and the "MCP Server Connector" window |

## The two lanes

```
Lane A — SCHEMA (no handshake)
  fm / adt ── FileMaker engine ── file (local path or fmnet://)
  schema, scripts, layouts, value lists, relations, persistentData…

Lane B — DATA (handshake required)
  MCP tools / typegen / deploy ── adt-mcp ── :1366 ── ADT.fmplugin
      ── "MCP Server Connector" web viewer ── local Data API script step
```

**Doctrine (ADT's own, confirmed in practice): CLI first for schema, MCP first
for data.** The lanes fail independently — schema batches run fine while the
data lane is wedged, and vice versa. A locked screen kills Lane B (and fmp
URLs) but never Lane A.

### When to use which

| Task | Lane |
|---|---|
| Create/change tables, fields, relations, scripts, layouts, value lists | **A** — `fm` (see `fm-cli` skill) |
| Project setup, provisioning, typed clients, HTML deploy | **A/B** — `adt` (see `adt-cli` skill) |
| SQL reads, Data API CRUD, table/layout metadata, DDL | **B** — MCP tools |
| Data reads when the connector is down or unattended | **A** — `evaluate:calculation` + `ExecuteSQL` through `fm` (no handshake needed) |
| Unattended / overnight work | **A only** — Lane B needs an unlocked console session |

Lane A needs only that a Pro-opened file be shared per-file (fmnet). Lane B
additionally needs ADT's components provisioned into the file and a live
connector handshake — see the `adt-connections` skill before debugging it.

## THE ROUTING RULE (in-FileMaker capabilities)

For any capability the agent needs from inside FileMaker: use either the normal
FileMaker plug-ins (MBS/BaseElements) or the ADT Helper — never a mix. If the
ADT CLI is installed, the ADT Helper is the lane.

The ADT Helper is this plugin's own FileMaker plug-in (`plugin/` in the repo):
window snapshots (`ADTH_WindowSnapshot`) and related agent-facing functions,
built precisely because ADT ships no way to *see* a native layout. On an
ADT-equipped machine it is the capability lane; MBS/BaseElements are the lane
only where ADT isn't in play.

One authoring note that spans both: the headless `fm` engine loads no plug-ins,
so any plugin calc call (`ADTH_…`, `MBS(…)`) written via `fm` must be wrapped in
`Evaluate ( "…" )` — compiles natively, resolves at runtime in Pro.

## Where the rest lives

- `fm-cli` — the NDJSON ops discipline and the schema-lane data-read trick
- `adt-cli` — project commands and adt.json anatomy
- `adt-connections` — handshake, privileges, force-refresh unwedge
- `adt-webviewer` — HTML apps end to end
- `adt-native-layouts` — layout authoring and its rendering traps
- `adt-quirks` — the master surprise list; check it before fighting a symptom
