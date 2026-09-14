---
name: adt-helper
description: >
  Use when an agent needs eyes or hands inside FileMaker Pro itself: screenshot or
  visually verify a native layout or web viewer ("does this layout look right?"),
  probe current state (layout, mode, found count, last error), start a FileMaker
  script without an fmp URL, read or write FileMaker's XML clipboard flavors
  (script steps, layout objects, tables, fields), or drive FileMaker through the
  ADT Helper drop-folder command channel. Also when installing or troubleshooting
  the ADT Helper plug-in, when ADTH_ functions return "?", or when fmp-URL script
  triggering has gone silently dead and another lane into Pro is needed.
---

# ADT Helper — the in-process FileMaker plug-in

ADT Helper is DataCraft's own FileMaker plug-in (plugin ID `ADTh`), shipped in
this Claude plugin's `plugin/` folder. It exists because ADT has no way to SEE
a native layout (structural validation passes while rendering is broken) and
because external script triggering (fmp URLs) can die silently. Everything it
does happens **inside FileMaker Pro's process**: window capture needs no macOS
Screen Recording permission, and the command channel needs no URL handler, no
MCP handshake, and no network.

**Routing rule (Joe's doctrine):** in-FileMaker capabilities come from either
the normal FileMaker plug-ins (MBS / BaseElements) or the ADT Helper — never a
mix. On an ADT machine, ADT Helper is the lane. Don't reach for MBS except for
the one gap ADT Helper documents (none currently known for agent work).

## Install / verify

```
cd plugin && make install-prebuilt     # or: make install SDK=<PlugInSDK path>
```

Restart FileMaker Pro. Verify: evaluate `ADTH_Version` in the Data Viewer — or
headlessly, author a script that sets a field to `Evaluate ( "ADTH_Version" )`.
The fm CLI's headless engine can't compile plugin calls, so **always wrap ADTH
functions in `Evaluate ( "…" )` inside fm-authored calculations**. A result of
`?` means the plug-in isn't loaded (check FileMaker Preferences → Plug-Ins).

## Function surface (v0.4.1)

Capture:
- `ADTH_WindowList` → JSON of open windows (pick a target by title).
- `ADTH_WindowSnapshot ( path { ; windowTitle } )` → PNG of a window's content
  view. Title matches case-insensitive contains; no title → frontmost.
- `ADTH_Snapshot ( path { ; optionsJSON } )` → adds `{"window":…, "x","y","w","h"
  (points, top-left origin), "scale":1}` region + scale control.
- `ADTH_WebViewerSnapshot ( path { ; windowTitle ; index } )` → rendered
  WKWebView pixels. Plain window capture draws web viewers BLANK — use this for
  them.
- `ADTH_WebViewerList ( { windowTitle } )` → JSON of a window's web viewers
  (index, url, title, size, loading) — discover the index before snapshotting.

Awareness / control:
- `ADTH_State` → JSON: file, layout, table, window, mode, foundCount,
  recordsOpen, lastError, scriptRunning, account, appVersion — plus wedge
  diagnostics (`modalWindow`, `sheetsOn`, `keyWindowClass`), plus
  `channelActive`/`channelFolder`/`channelAutoArmed` and `hostApp` (which
  FileMaker copy answered — see per-app scoping below).
- `ADTH_RunScript ( file ; script { ; param ; control } )` → queues a script via
  the plug-in SDK's StartScript — the fmp-URL-free trigger lane. `control`:
  resume (default) / halt / exit / pause.

Clipboard — **second choice, not the authoring lane.** Scripts, fields,
tables, value lists: author them with the fm CLI (`create:script` etc.), which
is validated, transactional, and diffable. Reach for the clipboard only when
paste-in is genuinely the only route (snippets from community/other tools,
layout-object shapes fm can't author). FileMaker uses its own clipboard
flavors — historically the reason MBS was needed; ADT Helper handles them
natively now (FileMaker XML flavors — codes `XMSS` steps, `XMSC` scripts, `XML2`
layout objects, `XMTB` tables, `XMFD` fields, `XMVL` value lists, `XMFN`
custom functions; carried as legacy `CorePasteboardFlavorType 0x<hex>`
pasteboard types, payload plain UTF-8 fmxmlsnippet XML — verified against a
real FileMaker 26 copy/paste both directions):
- `ADTH_ClipboardFormats` → what's on the clipboard, FM flavors flagged.
- `ADTH_ClipboardGetXML ( { code } )` → the XML (auto-detects when no code).
- `ADTH_ClipboardSetXML ( xml { ; code } )` → stages XML for paste-in; flavor
  sniffed from the root element when omitted.

## The command channel — the agent's main lane

`ADTH_ChannelStart ( folder )` arms an idle-loop worker. The agent writes
`<name>.json` into the folder; the plug-in executes and writes
`results/<name>.json` (`{"ok":…, "result"|"error":…, "command":…}`), moving the
command to `processed/`. Up to 5 commands per idle tick; the channel starves
while a FileMaker script is running and catches up after.

Commands (`cmd` key): `version` · `state` · `windowlist` ·
`evaluate {expr}` · `sql {query, file?}` (ExecuteSQL, tab/newline separators) ·
`runscript {script, file?, param?, control?}` · `snapshot {path, window?,
x/y/w/h?, scale?}` · `websnapshot {path, window?, index?}` ·
`clipboard-formats` · `clipboard-get {code?}` · `clipboard-set {xml, code?}`.

Layout-targeted screenshot = `runscript` a go-to-layout script, then `snapshot`.

Write-then-rename so the scanner never reads a half-written file (dot-prefixed
names are ignored — write to `.tmp`, `mv` into place). Poll `results/` for the
same filename; ~0.1 s intervals, 15 s timeout is a good default.

**Bootstrap doctrine:** the channel is off until armed — and 0.4.0 gives two
ways to arm it. There is still no standing execution surface without an
explicit, file-backed opt-in.

**Auto-arm (0.4.0+, preferred — no script at all).** Write
`~/.adt-helper/config.json`:

```json
{ "autoArm": true, "files": ["MyFile", "OtherFile"] }
```

**Per-app scoping (0.4.1) — the setup that matters when FileMaker is
duplicated.** Joe runs several copies of FileMaker as independent clients
("FileMaker Pro", "FileMaker Pro Agent", …). They SHARE the version-keyed
Extensions folder, so one plug-in binary loads into every copy. Scope
auto-arm by host app so the agent's copy arms itself and the human's never
does:

```json
{
  "autoArm": false,
  "apps": {
    "FileMaker Pro Agent": { "autoArm": true, "files": ["*"] },
    "FileMaker Pro":       { "autoArm": false }
  }
}
```

An `apps` entry overrides the top-level keys for that copy; a copy with no
entry inherits the top level. `ADTH_State`/`ADTH_ChannelStatus` report
`hostApp` so you can tell which copy answered. Channel folders are
namespaced `~/.adt-helper/<app>/<file>` (0.4.1) so two copies with the SAME
file open never race for one command queue — critical, since a hosted file
can be open in both at once. Channels are per-process, so each copy has its
own.

The idle loop checks this config (throttled, ~3s) whenever the channel is NOT
active; if `autoArm` is true and the frontmost file is allowlisted, it arms
`~/.adt-helper/<file-name>` by itself. `"*"` allows any open file; `folder`
overrides the path. **The config file IS the consent** — no config, nothing
ever arms. It is standing: it survives FileMaker restarts and re-arms
continuously, so a session never needs a human or a script again. An explicit
`ADTH_ChannelStop` suppresses auto-arm until the config's mtime changes
(edit it to re-consent) or FileMaker restarts. `ADTH_State` and
`ADTH_ChannelStatus` report `channelAutoArmed`. Keep the folder `chmod 700`
and the config `chmod 600` — both are credentials (see Safety rules).

**LIMITATION — the channel is a single global.** One folder, one file, per
FileMaker process: whichever file arms first holds it, and auto-arm bails
while a channel is active (`channelFolder` in `ADTH_State` names the holder).
If an old startup-script file grabs it, the allowlisted file never arms —
release it (`ADTH_ChannelStop`, then touch the config to re-consent) or
retire that file's arm script.

**Script arming (pre-0.4.0 lane, still supported).** Author an `ADTH Channel
Start` script (`Set Variable [ $r ; Evaluate ( "ADTH_ChannelStart (
\"<folder>\" )" ) ]`) and either run it once or append it to the file's
startup script (OnFirstWindowOpen) — note wiring OnFirstWindowOpen is a
GUI-only step (fm quirk 34), which is exactly what auto-arm removes. Folder
convention either way: `~/.adt-helper/<file-name>` — outside Dropbox,
per-file.

Commands: add `webviewerlist {window?}` (discover snapshot indices) and `help`
(lists the command grammar) to the set above.

A timeout on every command means: Pro not running, channel not armed (run the
arm script; check `ADTH_ChannelStatus` in the Data Viewer), or — **verified
limitation** — a modal dialog is up: modals starve FileMaker's plug-in idle,
so the channel goes silent and queued commands drain only after dismissal.
During a wedge the outside signals are `GET :1366/health` (`idleState:
"unsafe"` — the ADT bridge's HTTP thread keeps answering) and screen eyes;
`ADTH_State.modalWindow` confirms post-hoc. Sheets don't starve idle and show
up live in `sheetsOn`.

## Script SOP (Joe's doctrine — always)

Every script the agent authors or triggers starts with `Set Error Capture [On]`
and `Allow User Abort [Off]`, and logs `Get(LastError)` somewhere the agent can
read back (a probe field, a stamped record, a channel result). Verify by
reading that log, never by absence of dialogs. Before firing any fmp URL or
script start, confirm the script exists in the **served** file (fmnet read) —
a URL naming a missing script raises a modal that wedges FileMaker's idle loop
and external triggering until a human dismisses it.

## Safety rules

- Snapshot paths and channel folders must live in the user's own space; never
  point the channel at a synced/shared folder another process writes to.
- `runscript` and `evaluate` execute with the privileges of the account signed
  into Pro — treat the channel folder itself as a credential and keep it out
  of any repo.
- The channel never runs unattended-by-design: it lives only while FileMaker
  Pro is open on the user's machine.
