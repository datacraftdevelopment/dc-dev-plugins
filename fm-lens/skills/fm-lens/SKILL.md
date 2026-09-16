---
name: fm-lens
description: >
  Use when an agent needs eyes or hands inside FileMaker Pro itself: screenshot or
  visually verify a native layout, one layout object, or a web viewer ("does this
  layout look right?"), probe current state (layout, mode, found count, last error),
  switch layouts or modes, make a new record, open or close a file or window, see or
  dismiss a dialog that has wedged FileMaker, start a script without an fmp URL, or
  read and write FileMaker's XML clipboard flavors. Covers the FM Lens drop-folder
  command channels. Also use when installing or troubleshooting the FM Lens plug-in
  (formerly ADT Helper), when FMLens_ or ADTH_ functions return "?", or when
  fmp-URL script triggering has gone silently dead.
---

# FM Lens: the in-process FileMaker plug-in

FM Lens (formerly **ADT Helper**, renamed 2026-09-16 at 0.5.0) is DataCraft's
own FileMaker plug-in, shipped in this Claude plugin's `plugin/` folder. It
exists because ADT has no way to SEE a native layout (structural validation
passes while rendering is broken) and because external script triggering can
die silently. Everything happens **inside FileMaker Pro's process**: window
capture needs no macOS Screen Recording permission, and the command channels
need no URL handler, no MCP handshake and no network.

**Routing rule (Joe's doctrine):** in-FileMaker capabilities come from either
the normal FileMaker plug-ins (MBS / BaseElements) or FM Lens, never a mix. On
an ADT machine, FM Lens is the lane.

## Install / verify

```bash
cd plugin && make install-prebuilt
```

(or `make install SDK=<PlugInSDK path>` to build). Both targets also remove an
old `ADT Helper.fmplugin`: the two share plug-in ID `ADTh` and must never be
installed together. Restart FileMaker Pro (every copy; they share one
Extensions folder).

Verify: evaluate `FMLens_Version` in the Data Viewer (`FM Lens 0.5.0`), or send
`{"cmd":"version"}` on a channel. The fm CLI's headless engine can't compile
plug-in calls, so **always wrap FMLens functions in `Evaluate ( "…" )` inside
fm-authored calculations**. A result of `?` means the plug-in isn't loaded.

**Calcs written for ADT Helper keep working.** FileMaker stores the plug-in ID
and function ID, not the name, and FM Lens kept both. Old `ADTH_…` calls
display as `FMLens_…` after the upgrade. Only `Evaluate ( "ADTH_…" )` text
strings need editing, because those are resolved by name.

## Calc functions

Capture:
- `FMLens_WindowList` → JSON of open windows.
- `FMLens_WindowSnapshot ( path { ; windowTitle } )` → PNG of a window's content
  view (title: case-insensitive contains; none → frontmost).
- `FMLens_Snapshot ( path { ; optionsJSON } )` → adds `{"window", "x","y","w","h"
  (points, top-left origin), "scale"}`.
- `FMLens_WebViewerSnapshot ( path { ; windowTitle ; index } )` → rendered
  WKWebView pixels. Plain window capture draws web viewers BLANK.
- `FMLens_WebViewerList ( { windowTitle } )` → the window's web viewers (index,
  url, title, size, loading).

Awareness / control:
- `FMLens_State` → JSON: file, layout, table, window, mode, foundCount,
  recordsOpen, lastError, scriptRunning, account, appVersion, wedge diagnostics
  (`modalWindow`, `sheetsOn`, `keyWindowClass`), channel state, and `hostApp`.
- `FMLens_RunScript ( file ; script { ; param ; control } )` → queues a script
  (control: resume, halt, exit, pause).

Clipboard (**second choice**: author with the fm CLI where it can):
`FMLens_ClipboardFormats`, `FMLens_ClipboardGetXML ( { code } )`,
`FMLens_ClipboardSetXML ( xml { ; code } )`. Codes: `XMSS` steps, `XMSC`
scripts, `XML2` layout objects, `XMTB` tables, `XMFD` fields, `XMVL` value
lists, `XMFN` custom functions.

Channel: `FMLens_ChannelStart ( folder )`, `FMLens_ChannelStop`,
`FMLens_ChannelStatus`.

## The command channels: the agent's main lane

Write `<name>.json` into a channel folder (write to a dot-file, then rename;
dot-names are ignored). The plug-in writes `results/<name>.json`
(`{"ok", "result"|"error", "command"}`) and moves the command to `processed/`.
Poll every ~0.1 s with a 15-30 s timeout. From 0.5.0, list and state results
are **JSON objects**, not strings.

| Channel | Folder | Runs on | Takes |
|---|---|---|---|
| **file** | `~/.fm-lens/<app>/<file>` | FileMaker's idle loop | every verb |
| **app** (0.5.0) | `~/.fm-lens/<app>/_app` | a Cocoa timer that **keeps running while a dialog is up**, and before any file is open | UI verbs only |

**UI verbs (both channels):**
- `version`, `windowlist`, `help`
- `dialogs`: modal windows, sheets and panels, with their texts, buttons and
  fields (`secure` marks a password box).
- `dialog-press {button, dialog?}`: clicks a button. **It never types**, so a
  sign-in prompt can be cancelled but never answered.
- `menu {path: ["Records", "New Record"]}`: any menu item, by titles.
- `gotolayout {layout}`: View › Go to Layout. **No script start, so no 825.**
- `mode {mode}`: browse, find, layout or preview.
- `newrecord`: FileMaker draws no body for a found set of zero, so make a record
  before checking body objects.
- `closewindow {window}` and `openfile {path}`: both stay in THIS FileMaker
  copy. Open goes by bundle path, never by bundle id (quirk 70).
- `snapshot {path, window?, x/y/w/h?, scale?}` → `{path, bytes, width, height}`.
- `webviewerlist {window?}`, `clipboard-formats`, `clipboard-get {code?}`,
  `clipboard-set {xml, code?}`.

**File-channel verbs:**
- `state`
- `evaluate {expr}`
- `sql {query, file?}`
- `runscript {script, file?, param?, control?}`: a failure returns
  `diagnostics` (account, privilege set, extended privileges, `hasFmplugin`,
  and a hint for 825).
- `snapshot {path, object, pad?}`: crops to one **named** layout object via
  `GetLayoutObjectAttribute` bounds, shifted down past the status toolbar.
- `websnapshot {path, window?, index?}`

A layout-targeted screenshot is now `gotolayout` then `snapshot`, with no
script involved.

**When the file channel times out, ask the app channel.** A timeout means Pro
isn't running, the channel isn't armed, or a modal dialog is up: modals stop
FileMaker's idle calls, so the file channel goes silent. Send `dialogs` to
`_app`, read what's up, and `dialog-press` the safe button (usually Cancel or
OK). Queued file-channel commands drain once it's gone.

## Consent: `~/.fm-lens/config.json`

**The config file IS the consent.** Without it, nothing arms and the app
channel does nothing. FM Lens falls back to the old `~/.adt-helper/config.json`
while the new file is missing. Scope it per FileMaker copy, since all copies
share one plug-in binary:

```json
{
  "autoArm": false,
  "apps": {
    "FileMaker Pro Agent": { "autoArm": true, "files": ["*"] },
    "FileMaker Pro":       { "autoArm": false }
  }
}
```

- An `apps` entry overrides the top-level keys for that copy, and `hostApp` in
  results says which copy answered.
- With `autoArm` true, the idle loop (checked every ~3 s) arms a file channel
  for the frontmost allowlisted file. `"*"` allows any file; `folder`
  overrides the path.
- The same consent switches on that copy's app channel.
- `FMLens_ChannelStop` suppresses auto-arm until the config's mtime changes.
- Keep folders `chmod 700` and the config `chmod 600`. They are credentials.

**Limitation: one file channel per FileMaker process.** Whichever file arms
first holds it. `channelFolder` in `state` names the holder. Release it with
`FMLens_ChannelStop`, then touch the config.

## Visual verification recipe

1. Build one-layout fixtures with `fm`, and send `theme` on the op that adds
   objects. Otherwise nothing draws (quirk 106; see `adt-native-layouts`).
2. Open each file with `openfile` on the app channel, or by AppleScript to the
   copy by name.
3. `gotolayout`, then `newrecord` if you need the body, then `snapshot`
   (whole window, or `object` for one element).
4. Check the result's `bytes` and dimensions. Look at the PNG, or count pixels.
5. `closewindow` the file.

`fm-ADT-testing/tests/visual.py` runs this loop.

## Script SOP (Joe's doctrine, always)

- Every script the agent authors or triggers starts with `Set Error Capture
  [On]` and `Allow User Abort [Off]`.
- Log `Get ( LastError )` somewhere the agent can read back. Verify by reading
  that log, never by the absence of dialogs.
- Before any script start, confirm the script exists in the **served** file.
  A missing script raises a modal that wedges the idle loop.

## Safety rules

- Snapshot paths and channel folders live in the user's own space, never in a
  synced or shared folder.
- `runscript` and `evaluate` run with the signed-in account's privileges.
  Treat channel folders as credentials and keep them out of repos.
- `dialog-press` is for unwedging, not for accepting things on the user's
  behalf. Don't press a button that deletes, saves over, or grants anything
  without the user's say-so.
- The channels only exist while FileMaker Pro is open on the user's machine.
