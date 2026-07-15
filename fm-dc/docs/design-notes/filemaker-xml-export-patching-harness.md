# FileMaker XML Export & Patching Harness

**Status:** working design notes
**Date:** 2026-07-15
**Target platform:** FileMaker 2026 (v26.0.1) — Pro + Server
**Audience:** me, and the coding agent driving this

---

## 1. What we're building

An agent-driven loop that can read a hosted FileMaker file's structure as XML, reason
about it, patch it, and verify the patch actually landed.

Two distinct jobs, often conflated:

| Job | Tool | Direction |
| --- | --- | --- |
| Read the structure | `Save a Copy as XML` (SaXML) / `FMDeveloperTool --saveAsXML` | code out |
| Write the structure | `FMUpgradeTool --update` | code in |

The loop: **read → diff → patch → read back → verify → repeat.**

Verification is the load-bearing wall. See §7 — the tools lie.

---

## 2. Triggering the export: two lanes

### Lane A — OData (server-side)

`POST https://host/fmi/odata/v4/{db}/Script.{scriptName}` with body
`{"scriptParameterValue": "..."}`.

Critical fact: **when OData runs a script, it runs as a server-side script.** So the
compatibility that matters is the FileMaker Server column, not the Data API column.

Consequences:

- `Save a Copy as XML` is Server: **Yes** (has been since 19.5). Works.
- File access is **sandboxed** to the Documents folder or the temporary folder, plus
  child folders. Paths containing `..` are invalid. Incomplete paths resolve relative
  to the temp path.
- On macOS, Documents = `/Library/FileMaker Server/Data/Documents/`
- So the agent **cannot** pass an arbitrary local path. It can pass a subfolder name.

### Lane B — ProofKit MCP (local)

ProofKit MCP is a **local** MCP server bound to the FileMaker Pro instance open on your
desktop. You run a "connect to MCP" script in the open file and the agent gets tools
pointed at that file.

Consequences:

- Scripts triggered this way run **in your Pro client**, not in the FMSE.
- Client-side, SaXML has **no sandbox** — it writes anywhere on local disk.
- Cost: speed. Beezwax measured a ~73MB solution at ~3.6s on server vs ~9 minutes
  through Pro against a hosted file.

### Decision

**Use Lane B as the trigger, Lane A as the engine.** ProofKit calls one client script;
that script pushes the expensive work to the server via PSoS and pulls the result back.
Details in §4.

**Measure first.** If your file exports locally in under ~30s with catalog selection on,
skip the PSoS complexity entirely and just write to disk from Pro. There is no transport
problem on the local path.

---

## 3. FileMaker 26 changed the export (this is the unlock)

Claris calls it the **"XML 2.0 grammar."** What shipped:

- **Catalog selection.** 20 catalogs. Export one, any combination, or the whole file.
- **Split output** into a separate file per catalog, plus a `Summary.xml` listing what
  was produced, plus a root-element attribute indicating whether catalogs were split.
- **UTF-8** output instead of UTF-16 LE. Removes a decoding step.
- Table View column details (field reference, visibility, width) and View By sort order.
- **The script step got the new options too**, including `Specify options as JSON` —
  most options settable as a JSON object via calculation: which catalogs, whether to
  include DDR_INFO, whether to split, whether to store object binary data under the node.
- `FMDeveloperTool --saveAsXML` mirrors it: `-cl FieldCatalog -t fields.xml`

### Selection ≠ splitting — don't conflate them

- **Selection is the win.** Pulling just `ScriptCatalog` after a script change or
  `FieldCatalog` after a field change drops the payload from ~70MB to a few hundred KB.
  Layouts in particular are enormous; leave them out unless you need them.
- **Splitting breaks the container transport.** N files won't fit in one container field.

**Rule: selection ON, splitting OFF.** You get one small file.

This dissolves most of the hard problems downstream — zip is unnecessary, container
bloat is a non-issue, and diffs get sharper because the surface is smaller.

### Diff noise: partly fixed

DDRREF values used to change on every save, making analysis tools report phantom
changes. As of 22.x, **many** elements now derive DDRREF from the existing UUID of the
catalog member or its parent. "Many," not all — still normalize before hashing/diffing,
but far less aggressively than pre-22.

### Also set

- `Include details for analysis tools` → **OFF** unless your verifier reads `DDR_INFO`.
  It adds full script step text and calc references and inflates the file significantly.
- Same FileMaker version on both sides of any diff. The XML grammar changes between
  versions and Claris says so explicitly.

---

## 4. The transport pattern (hosted file, server-side generation)

### The trap

`Insert File` is **Server: No**. A server-side script cannot pick a file off disk and
drop it into a container. This is the wall everyone hits and it's why people reach for
BaseElements.

### The native fix

`Insert from URL` is **Server: Yes**, supports the `file` protocol, and the file
protocol *can* be used in server-side scripts to reference files in Documents or temp —
exactly where SaXML wrote it. Paths from `Get()` functions are in FileMaker format and
must be converted with `ConvertFromFileMakerPath ( $path ; URLPath )` first.

**Verdict on BaseElements: not needed.** The gap it would fill is already covered.
It has `BE_Zip`/`BE_Unzip`, is free and open source, and runs on FMS including Ubuntu —
worth it only if the server is remote over a slow link AND you're moving huge payloads.
With catalog selection you aren't. Treat as a later optimization, not a prerequisite.

### The shape

MCP calls **one** script. The script owns the whole round trip. MCP never touches the
container — it just gets the local path back as the script result.

```
# ---------- CLIENT (the only thing ProofKit calls) ----------
Perform Script on Server [ "SRV SaveXML" ; Parameter: $agentJSON ; Wait: On ]
Set Variable [ $pk ; Get(ScriptResult) ]
Go to Layout [ "XMLDrop" ]
Perform Find [ pk = $pk ]
Export Field Contents [ XMLDrop::File ; $localPath ; Create folders: On ]
Delete Record [ No dialog ]
Exit Script [ Text Result: $localPath ]
```

```
# ---------- SERVER ("SRV SaveXML", full access privileges ON) ----------
Set Variable [ $fmPath ; Get(TemporaryPath) & "build.xml" ]
Save a Copy as XML [ Window name: Get(WindowName) ;
    Destination file: "filemac:" & $fmPath ;
    Options as JSON: $agentJSON ]        # catalogs, DDR_INFO, split, binary
If [ Get(LastError) ≠ 0 ] ... End If
Go to Layout [ "XMLDrop" ]
New Record/Request
Insert from URL [ Select ; With dialog: Off ; Target: XMLDrop::File ;
    "file://" & ConvertFromFileMakerPath ( $fmPath ; URLPath ) ]
Commit Records
Exit Script [ Text Result: XMLDrop::pk ]
```

`Export Field Contents` is a Pro step with no sandbox — the client writes wherever the
agent wants. No OData, no plugin, no base64.

### Gotchas

- **Not global fields.** PSoS runs in its own FMSE session with no client context and no
  shared globals; a global set server-side is discarded when the session ends. The
  container must be a regular field in a regular table.
- **Record locking.** If the client is parked on the drop-box record, the server session
  can't write it. Keep that layout off-screen; navigate to it only inside the pull script.
- **Refresh.** The client won't auto-see a record created by another session. Re-find on
  the pk returned by PSoS.
- **Container storage.** Use external secure storage; delete after pull.
- **Error 3.** Unsupported steps in FMSE return error 3, skip silently, and continue.
  Check `Get(LastError) = 3`. Also check byte count > 0 — a zero-byte file is the real
  failure signal.
- **Schema pollution.** The drop-box table/field/layout become part of the schema you're
  exporting. Static, so not diff noise, but your instrumentation is inside your
  measurement. Production answer: put the drop box in a separate hosted file (server-side
  scripts can reach other files on the same host if the client already opened them).
  Demo answer: same file, accept it, note it out loud.

### Free in 26

`Export Field Contents` is now supported in scripts run by FileMaker Server, the Data
API, and the OData API. Still sandboxed server-side, so it doesn't change the above —
but a pure-OData headless variant is now cleaner if we ever need Pro not to be open.

---

## 5. Changelog table

### The design

A record per export run. Timestamp, catalogs requested, error codes, byte count, hash of
the normalized XML, git commit SHA, diff summary.

### Split the roles

- **FileMaker = the ledger.** Small, cheap, queryable, right there when the agent needs
  to reason about recent state.
- **Git = the archive.** The XML files themselves. Git diffs natively and survives the
  file being restored from backup.

**Why:** a history stored inside the artifact shares fate with the artifact. You reach
for the changelog precisely when a patch went wrong — and your recovery move (restore the
file) wipes the record of the thing you're investigating. Same for clone, rebuild, corrupt.

Container = convenience cache for the last N runs, not the system of record.

### Notes must be derived, not authored

Do **not** have the agent write "what I changed" from intent. FMUT reports a patch was
applied even when it changed nothing — a log of agent belief will confidently describe
changes that never landed, and be wrong exactly when it matters.

**Order: export → diff → annotate from the diff.** No hunk, no note.

### The hash is the cheap silent-failure detector

> Patch. Re-export the affected catalog. Normalize. Hash.
> If the hash equals the pre-patch hash, FMUT lied — nothing changed.

Normalize first (residual DDRREF churn). Diff agent-side; `git diff` already does this
well and FileMaker calcs on megabytes of XML are misery.

### Secrets warning

The **persistent data store** holds named values in the *schema*, so SaXML reaches them —
and they appear as **plain text** in the export. Don't put API keys there. If you're
committing exports to git, that's permanent.

Useful flip side: stamp a build ID via `Configure Persistent Data`. Every export then
self-identifies which changelog row produced it, and the stamp survives cloning.

---

## 6. The patch workflow (this is the demo)

### What FMUpgradeTool actually does

```
FMUpgradeTool --update -src_path ./MySourceApp.fmp12 \
  -patch_path ./MyPatch.xml -dest_path ./MyPatchedApp.fmp12
```

`-dest_path` **is a whole FileMaker file.** That's the output. There is no separate
"turn the patch into a file" step.

**The upgrade tool does not migrate, add, modify, or delete record data**, including
externally stored container data. So `--update` on a copy of production **keeps
production's data**. The Data Migration Tool step is unnecessary on this path.

Claris draws the line: upgrade tool = quick, short-term fixes between full releases,
patch file primarily for *adding* objects. DMT = full releases, or anything FMUT can't
touch.

### Do NOT use `--generateDBFile` here

Two reasons:

1. **Wrong input.** A patch file's root is `FMUpgradeToolPatch`; a full export's root is
   `FMSaveAsXML`. `generateDBFile` wants the latter. You can't feed it a patch.
2. **It's broken for layouts.** Placing a field on a layout doesn't work — the box is
   there, the field doesn't display. And the read-back lies: the field reference looks
   intact in a fresh saveAsXML while the layout renders empty. That's the one failure our
   whole verification strategy can't catch.

`generateDBFile` is a scaffold builder for DMT targets. It builds clean schema. It does
not reconstitute a solution. **Dropping it also drops its layout bug** — with a real
file, FMUT patches all elements including layout objects.

### The chain

1. `--generateGUIDs` on the prod copy **and** on dev — **required first**. A patch that
   deletes or modifies existing objects must reference them by GUID.
2. `Save a Copy as XML` on both. Same FM version. Catalog-selected.
3. Diff → author the patch XML.
4. `--update -src_path prodcopy.fmp12 -patch_path patch.xml -dest_path patched.fmp12`
5. Verify (§7).
6. Deploy: `fmsadmin close` → swap → `fmsadmin open`.

**The file must be closed to patch.** A patch against an open file simply fails. Rhythm:
close, patch, reopen, verify. On macOS, AppleScript owns close/reopen.

### Run it on the server

FMUpgradeTool installs with FileMaker Server:
`/Library/FileMaker Server/Database Server/bin/FMUpgradeTool` (macOS).

FM 26 added a **command-line-tools-only install** option (FMUT + FMDT + DMT) — pick it
in the Deployment Options dialog.

Patching in place on the server beats hauling a multi-GB file across the network. Close,
patch, reopen = a short maintenance window.

### Auth

Account needs full access or the `fmupgrade` extended privilege.

---

## 7. Verification — the honest picture

**The tools lie. Layer the checks.**

| Layer | What it catches | What it misses |
| --- | --- | --- |
| `XMLDeserializeResults.log` | catalogs processed, errors, item counts | undersells — has logged "Nodes succeeded: 0" on a delete that worked |
| Console "Patch File Applied" | nothing | reports success on no-ops |
| Re-export + normalized hash | silent no-ops (hash unchanged = nothing happened) | anything the XML represents correctly but the file renders wrong |
| **Open it and look** | layout binding | slow, manual |

### Known no-ops that report success (Codence testing)

- **ReplaceAction on a theme**, object- or catalog-level — no-op every time, validated
  and "applied," unchanged.
- **DeleteAction by object/member UUID** — no-op.
- DeleteAction at catalog level (catalog's own UUID) — worked, but logged 0 successes.
- AddAction at catalog level — worked, but the body had to be exactly as FileMaker
  authored it; hand-edits break it; duplicate-key adds hard-conflict.

**AddAction is the safe path.** Add a field, add a script, add a table occurrence.

### Other standing FMUT limits

- Can append steps to the end of a script; inserting mid-script requires
  delete-and-rebuild with the original ID.
- Custom functions can't be edited in place — delete and recreate.
- Silent failure is the single biggest obstacle to an autonomous loop.

### Skills, not vibes

Left to general knowledge, a model approximates patch XML — close, but not reliably
correct. A misshapen patch can fail loudly or, worse, apply something subtly wrong that
the tool still reports as success. Load a Skill with the real grammar per element type.
Claris republished all help docs in markdown (`help.claris.com/markdown/...`, index at
`help.claris.com/llms.txt`) — point the agent at the authoritative reference instead of
its memory.

---

## 8. Demo script for this afternoon

**Do:**

- generateGUIDs both sides first
- catalog-selected export (small, fast, readable on screen)
- AddAction patch
- `--update` → show the output IS a working file, with data intact
- hash check catching a deliberate no-op (great beat if you can stage it)
- open the file and look at the layout — name why you're doing it

**Don't:**

- demo `generateDBFile`
- demo ReplaceAction on a theme
- skip generateGUIDs
- mismatch FM versions across the diff

**Say it like this:** "I diff two hosted files, generate a surgical patch, apply it to a
copy of production with its data still in it, verify the change landed, and swap it in
during a 30-second window."

Not: "I rebuilt the file from XML." That's a demo that breaks the moment someone asks to
see a layout.

**Naming:** it's the **Upgrade** Tool (FMUpgradeTool). Not Update.

---

## 9. Direction

**Now**

- Build the one-script MCP surface (§4). Validate the AppleScript close/reopen cycle
  end-to-end before adding any plugin complexity.
- Catalog selection ON, splitting OFF, DDR_INFO OFF.
- Changelog ledger in FileMaker, XML archive in git.

**Next**

- Normalization pass + hash oracle wired into the loop.
- Patch-grammar Skill built from the markdown docs.
- Move the drop-box table out of the target file.

**Watching**

- Claris agentic tooling — "later this summer," not in 26.0. Likely ships as separate
  tools alongside Pro, not inside it.
- Claris may be working toward patching **hosted** files (no close required). Unconfirmed.
  If it lands, the AppleScript cycle becomes optional and the whole loop tightens.
- `generateDBFile` layout binding + trustworthy FMUT error reporting. If both land, XML →
  file → verify → deploy becomes real and the round-trip story is finally true.

**Open questions**

- Actual export time for *our* file, local vs PSoS, per catalog. Measure before optimizing.
- Which of the 20 catalogs we actually need per change type.
- What normalization is still required post-22 DDRREF fix.

---

## 10. References

- [Save a Copy as XML — script step](https://help.claris.com/en/pro-help/content/save-a-copy-as-xml.html)
- [Paths in server-side scripts](https://help.claris.com/en/pro-help/content/paths-in-server-side-scripts.html)
- [About running scripts on Server / Cloud](https://help.claris.com/en/pro-help/content/running-scripts-on-server.html)
- [Insert from URL](https://help.claris.com/en/pro-help/content/insert-from-url.html) · [Insert File](https://help.claris.com/en/pro-help/content/insert-file.html)
- [OData — Run scripts](https://help.claris.com/en/odata-guide/content/run-scripts.html) · [binary field value](https://help.claris.com/en/odata-guide/content/request-field-value-binary.html)
- [FileMaker Pro 2026 release notes](https://help.claris.com/en/pro-release-notes/content/index.html) · [Server](https://help.claris.com/en/server-release-notes/content/index.html)
- [FileMaker Upgrade Tool Guide](https://help.claris.com/en/app-upgrade-tool-guide/content/index.html) · [command-line parameters](https://help.claris.com/en/app-upgrade-tool-guide/content/command-line-parameters.html)
- [Claris docs in markdown — llms.txt](https://help.claris.com/llms.txt)
- Codence — [What's New in FM 26 for AI Development](https://codence.com/resources/blog/technology/filemaker-26-ai-development)
- Codence — [The Patch Method](https://codence.com/resources/blog/technology/filemaker-ai-foundations-the-patch-method)
- Beezwax — [FileMaker Server Save as XML](https://blog.beezwax.net/filemaker-server-save-as-xml/)
- Soliant — [Why FileMaker AI Agentic Coding Needs a Harness](https://www.soliantconsulting.com/blog/why-filemaker-ai-agentic-coding-needs-harness/)
