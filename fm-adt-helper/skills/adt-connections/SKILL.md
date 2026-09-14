---
name: adt-connections
description: >
  Use when bringing a FileMaker file onto ADT's data lane or debugging it — the
  connector handshake, the "MCP Server Connector" window, connectedFiles showing
  nothing, troubleshoot_setup verdicts, MCP tools failing or timing out ("Timed out
  waiting for FileMaker callback"), DBError 802, FileMaker script-start error 825,
  idleState "unsafe", or scripts/fmp URLs that silently stop firing. Covers the full
  lifecycle (share → record → provision → handshake), the extended-privilege grants a
  blank file needs, the force-refresh unwedge, and the guard-card and locked-screen
  failure modes that no diagnostic reports.
---

# ADT connections — the handshake gauntlet and every way it fails

The **schema lane** (`fm`/`adt`) needs only per-file sharing. Everything below
is about the **data lane**: MCP tools, typegen, deploy. Check first whether the
task even needs it — data reads can ride the schema lane
(`evaluate:calculation` + ExecuteSQL, see `fm-cli`), and deploy can go through
`update:persistentData`.

## The happy path

1. **Share the file individually.** FileMaker Pro → File → Sharing → Share with
   FileMaker Clients → select the file → All users. App-wide Network Sharing
   "On" is NOT enough; until per-file sharing is on, `fmnet://` fails with
   **DBError 802**. `connectedFiles.suggestions` diagnoses this exactly, per file.
2. **`adt init .`** — records the target (works before the file is reachable).
3. **`adt connect "fmnet://localhost/<name>"`** — confirms credentials.
   → *The schema lane is now fully live.*
4. **`adt components apply --file <name>`** — provisions connector scripts and
   layouts through fm; no Pro cooperation needed.
5. **Handshake** — the "Connect To ADT" script opens the "MCP Server Connector"
   window (a web viewer named `web`), which registers with the plugin's local
   service on port 1366. ADT auto-starts this script (doctor/troubleshoot);
   nobody clicks anything in the happy case.
6. `connectedFiles` lists the file; SQL/Data API/typegen/deploy work.

## Blank files can't handshake out of the box — grant privileges first

A factory-blank file has every extended privilege off except `fmapp`, ADT's
provisioning never touches privileges, and no ADT diagnostic mentions them. The
auto-start fails repeatedly with FileMaker error 825 (visible at
`service.fileMaker.lastScriptStart` / `GET 127.0.0.1:1366/health`). Cheap
insurance on any blank file, via the schema lane, before expecting a handshake:

```
{"op":"update:extendedPrivilege","name":"fmurlscript","privilegeSets":["[Full Access]"]}
{"op":"update:extendedPrivilege","name":"fmplugin","privilegeSets":["[Full Access]"]}
```

(`fmurlscript` is needed for fmp-URL script starts anyway; the 825s cleared
right after the `fmplugin` grant.)

## Force-refresh: the universal unwedge

After a good handshake, data tools can still time out ("Timed out waiting for
FileMaker callback") while the doctor reports all-green — its probes use a
lighter path than the data tools' socket. Reliable recovery, no user needed:

```
open 'fmp://$/<file>?script=Connect%20To%20ADT&param=force-refresh'
```

`force-refresh` is an officially supported parameter of the provisioned script;
it closes and reopens the connector window. It cleared every observed wedge,
including one mid-`adt deploy`. Treat a callback timeout as "connector wedged",
not "request wrong": timed-out writes had NOT executed (verified by row
counts), so retry after refresh is safe. One timeout right after a fresh
handshake is just cold start — retry once before refreshing.

## The guard-card failure mode (invisible to every diagnostic)

The connector protects its layout with an **in-page HTML confirm card**:
navigate the connector window away (or close it) and an "Are you sure? … MCP
tools will stop working" card appears INSIDE the web viewer. While it sits
there, script starts and data tools die *silently* — yet `/health` reports
`user_idle` (it's an HTML card, not a FileMaker dialog) and `bridgeStatus`
still says `webviewerConnected: true`. This caused a 4-hour "all triggers dead"
outage; a window screenshot (ADT Helper) diagnosed it in one frame.
**Corollaries:** never let an agent-authored script navigate or close "whichever
window is frontmost" — the connector may be frontmost; and when diagnostics are
green but nothing fires, *look at pixels*.

## Other outage causes, in triage order

1. **Locked screen** kills the data lane and fmp URLs — but not the schema
   lane. `/health` stays green. Check
   `ioreg -n Root -d1 -a | grep -A1 IOConsoleLocked` before anything else.
   Unattended work must ride the schema lane exclusively.
2. **idleState "unsafe"** — a modal dialog blocks all script starts. Watch for
   your own booby traps: an agent-authored trigger that runs Show Custom Dialog
   wedges the very channel the agent needs. Keep dialogs out of triggers on
   agent-managed files.
3. **`troubleshoot_setup` is not passive** — calling it fires a connector
   auto-start for the named file. Fine normally; confusing when you're using it
   to *observe* the handshake.

## Diagnostic toolbox

| Probe | Tells you |
|---|---|
| `connectedFiles` | Handshake state + per-open-file reachability with reasons |
| `troubleshoot_setup` (name the file) | Full per-file verdict; also fires an auto-start |
| `GET http://127.0.0.1:1366/health` | Plugin alive, idle state, last script-start error — curl-able, no MCP needed |
| `fm --dry-run` with one read | Is the schema lane alive (independent of all the above) |
| `adt doctor --json` | Machine-readable everything, from the shell |
