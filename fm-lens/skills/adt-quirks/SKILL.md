---
name: adt-quirks
description: >
  The master list of ADT edges, quirks, and gotchas — consult whenever ADT behaves
  surprisingly: an fm batch fails or rolls back unexpectedly, a layout object won't
  render or clips, MCP tools time out while diagnostics look green, scripts or fmp URLs
  silently stop firing, adt components remove fails, deploy wedges, pnpm blocks a
  scaffold install, a .fmp12 in Dropbox misbehaves, or an error code (802, 825, 207,
  106, 805) doesn't match the obvious explanation. Every entry was found the hard way
  and says how. Check here BEFORE fighting a symptom from first principles.
---

# ADT quirks, edges, and gotchas — master list

Found by hands-on exploration of ADT 0.4.0 (build 29793558). Numbered for
reference; categories: **[env]** environment, **[conn]** connection, **[fm]**
fm CLI, **[adt]** adt CLI, **[mcp]** MCP tools, **[app]** web viewer apps,
**[proc]** process.

FM Lens, the DataCraft FileMaker plug-in, was called **ADT Helper** before
2026-09-16. Older notes use that name, `ADTH_` functions and `~/.adt-helper/`.

1. **[conn] Per-file sharing, not app-wide.** Network Sharing "On" serves
   nothing by itself; each file is shared individually (File → Sharing →
   All users). Until then: DBError 802, and `connectedFiles.suggestions`
   explains it per file.
2. **[conn] Blank files can't handshake out of the box.** A factory file has
   every extended privilege off except `fmapp`. The plugin's auto-start of
   "Connect To ADT" failed repeatedly with FileMaker error 825 until
   privileges were granted (the errorCode flipped to 0 after `fmplugin` was
   granted to [Full Access]; `fmurlscript` had been granted earlier and is
   needed for fmp-URL starts anyway). ADT's provisioning writes scripts and
   layouts but never touches privileges, and no diagnostic mentioned them.
3. **[conn] Doctor "ready" ≠ data tools working.** The webviewer ping and
   `ADT_probe` use a lighter path than the data tools' callback socket, so
   `troubleshoot_setup` can be all-green while `table_metadata`/orchestrator
   time out ("Timed out waiting for FileMaker callback").
4. **[conn] The connector wedge has a no-user fix.** The provisioned script
   accepts `force-refresh`: `open 'fmp://$/<file>?script=Connect%20To%20ADT&param=force-refresh'`
   closes and reopens the connector window. Cleared the wedge every time it
   appeared (including once mid-`adt deploy`).
5. **[conn] Timed-out writes did not execute.** A create that timed out left
   no record (verified by SQL count) — retry after refresh is safe, not a
   duplicate risk. (Observed twice; not a guarantee.)
6. **[conn] Agent-authored triggers can wedge the agent's own channel.** An
   `OnRecordLoad` → Show Custom Dialog trigger left FileMaker in idleState
   "unsafe", blocking all script starts until the modal was dismissed. Don't
   put dialogs in triggers on agent-managed files.
7. **[conn] `troubleshoot_setup` is not passive** — calling it fires a
   connector auto-start attempt for the named file. Fine normally; confusing
   when you're using it to *observe* the handshake.
8. **[fm] Batches are transactional even for reads.** One bad op in a batch of
   reads → exit 1, `rolledBack: true`. Read results still stream, but plan
   batches accordingly.
9. **[fm] Calculation values in field options are objects and `context` is
   required** — even for `Get(UUID)`: `{"text":"Get ( UUID )","context":"<occurrence>"}`.
   (Layout-object calc settings — tooltips, hideCondition — are plain strings
   instead. Two shapes for "a calculation" depending on where you are.)
10. **[fm] A context created earlier in the same batch isn't fully usable** for
    resolving field references through it (engine answers 106). Split
    relation-dependent calc fields into a later run.
11. **[fm] `sortRelated` on a relation is just a boolean.** The sort *spec*
    (which field, which order) is not in the create surface.
12. **[fm] Inline layout-object nesting is one level per op.** Container
    interiors (tab/slide panel contents, popover contents) are a second op with
    `parent:<id>`. Popovers: the popover object is auto-minted next to its
    button and its id arrives in `createdObjectIds`.
13. **[fm] Field auto-labels occupy ~208pt left of the field** and count in
    container bounds checks (error helpfully reports the container's interior).
    At layout top level they may land at negative x without complaint.
14. **[fm] `createdObjectIds` is not in input order** — map ids by reading
    contents back.
15. **[fm] Icons/pictures are write-by-path, read-by-id.** `icon` (PNG/SVG) and
    `picture` embed the file; reads report `iconId`/embedded data, so don't
    expect a literal round-trip of the path.
16. **[fm] FileMaker 2025 blank files have exactly one theme (Apex Blue)** and
    Apex Blue is the only built-in the CLI will install — the classic names
    (Enlightened, Vibrant, …) are refused. No custom theme creation, no style
    creation, no per-object colors/fonts: cosmetics are theme-bound.
17. **[fm] `delete:table` succeeds silently with dependents.** The layout bound
    to the deleted table survives with `tableOccurrence: null` and orphaned
    field objects (`field.name` becomes ""). No warning, no cascade to the
    layout. Check layouts after table deletes.
18. **[fm] No parts, no colors, no list-view config** in the layout surface —
    body height only, theme cosmetics only. "Layout automation" ≠ "design
    automation".
19. **[fm] read:layout detail puts objects under `contents.objects`**, and
    named reads across catalogs return a single object rather than
    `items:[...]` — two shapes for read results.
20. **[fm] Error messages are the API tutor.** Unknown keys list every accepted
    key; wrong enum values name the vocabulary (mostly); wrong shapes name the
    wanted key. Dry-run probing is an effective discovery loop, and this
    appears to be by design ("unknown keys are refused rather than ignored").
21. **[adt] `adt init` keeps your CLAUDE.md** and says so; it git-inits the
    folder; connect failure doesn't fail init.
22. **[adt] Doctor telemetry is curl-able**: `GET 127.0.0.1:1366/health` gives
    idle state + last script-start error without any MCP session.
23. **[adt] `defaultPanel` is tab-controls-only**; slide controls refuse it
    (they always open on their first panel).
24. **[app] pnpm 10 trust policy can block the scaffold's install**
    (`ERR_PNPM_TRUST_DOWNGRADE` on `semver@6.3.1` observed). Workspace-level
    `trust-policy-exclude[]=` preserves the global policy. Engine warnings
    (wants Node 22/24) and husky's ".git can't be found" are noise.
25. **[app] The scaffold's phase ledger is the recovery map** —
    `adt-project-setup-summary.json` names each phase's status and fix
    commands; `adt doctor --setup-log --phase <id>` prints the detail. Never
    re-scaffold to recover.
26. **[mcp] First data call after a fresh handshake may time out**; the retry
    succeeded. Treat one timeout as cold start, repeated timeouts as the wedge
    (quirk 4).
27. **[mcp] SQL lane evaluates unstored cross-relation calcs correctly** —
    worth knowing since ExecuteSQL-over-calc-fields is a classic FileMaker
    performance foot-gun; on small data it was instant and right.
28. **[env] Old themes gone, engine pinned**: the fm CLI reports its pinned
    engine (26.0.1) in `--help`; files on servers older than FM Server 26 are
    refused by design in 0.4.0.
29. **[conn] The connector guards its layout with an in-page confirm card that
    no diagnostic can see.** Navigating the connector window away from its
    layout (or closing it) raises an "Are you sure? … MCP tools will stop
    working" card INSIDE the web viewer. While it sits there, script starts
    and data tools die silently — but `/health` reports `user_idle` (it is an
    HTML card, not a FileMaker dialog) and `bridgeStatus` still says
    `webviewerConnected: true`. Root cause of a 4-hour "all triggers dead"
    outage; FM Lens's first-ever screenshot diagnosed it. Corollary:
    never let an agent-authored script navigate the frontmost window blindly —
    the connector may be frontmost.
30. **[fm] Apex Blue minimum object heights (measured from screenshots):**
    single-line edit boxes/dropdowns need ~30pt (22–24 clips the glyphs),
    portal-row fields ~28pt, radio-button sets ~26pt per value stacked
    (4 values ≈ 108pt). The engine's bounds validation accepts any height —
    clipping is invisible to every structural read, which is exactly why the
    snapshot loop exists.
31. **[fm] `update:script` with a `body` requires the `token`** from the same
    script's `read … detail:true` — optimistic concurrency is mandatory for
    body replacement.
32. **[fm] Plugin calc functions can't be authored directly** —
    the headless engine refuses `MBS(…)`/`FMLens_…(…)` with
    `calc_unknown_function` (no plugins loaded). Wrap the call in
    `Evaluate ( "…" )`: compiles natively, resolves at runtime in Pro. This is
    the general pattern for plugin-dependent scripts via fm.
33. **[fm] `evaluate:calculation` + `ExecuteSQL` = headless data reads over
    the schema lane** — no plugin lane, no handshake, works even when the
    connector is wedged. The fm engine opens the file as a client and
    evaluates for real.
34. **[fm] File Options are outside the surface.** The file's opening layout
    ("Switch to layout"), OnFirstWindowOpen/OnLastWindowClose triggers, and
    auto-login live in FileMaker's File Options dialog — no fm catalog covers
    them. Consequence: a file reopens on whatever layout its front window last
    showed, so an agent session that leaves the connector layout frontmost
    turns the MCP Server Connector into the user's first window on next open.
    Remedy pattern: an fm-authored "Startup" script (Go to Layout → Perform
    Script [Connect To ADT] → Select Window [Get(FileName)]) — but wiring it
    to OnFirstWindowOpen is a GUI-only step.
35. **[fm] The snapshot loop's own window discipline:** capture the frontmost
    window rather than matching titles (duplicate/leftover windows titled like
    the file hijack byName and contains-matches — identical PNG byte sizes are
    the tell), and Adjust Window [Resize to Fit] before shooting or captures
    crop to the user's window size.
36. **[env] No screenshot feature anywhere in ADT** — no MCP tool, no fm op,
    no CLI verb renders a native layout; the browser-preview feedback loop
    exists only for web viewer apps. The FM Lens plug-in (shipped in this
    plugin's `plugin/` folder) closes the gap with in-process window snapshots.
37. **[conn] THE unified outage cause: a locked screen kills the plugin lane
    and fmp URLs — but not the schema lane.** `CGSSessionScreenIsLocked=true`
    correlates exactly with every "all triggers dead" episode: fmp URLs need
    an active console session to activate FileMaker, and the connector's web
    viewer callbacks throttle when the session locks — while `/health` stays
    green (the plugin's HTTP thread is unaffected) and `webviewerConnected`
    stays true. Check `ioreg -n Root -d1 -a | grep -A1 IOConsoleLocked` before
    diagnosing anything else. Consequence: unattended/overnight agent work
    must ride the schema lane exclusively (which includes deploy — quirk 40).
38. **[fm] Dropbox corrupts `--create`.** A .fmp12 created inside a Dropbox
    folder reopened as DBError 805 (damaged) — sync grabbed it mid-write.
    Create scratch files outside Dropbox and move them in afterwards.
39. **[adt] `components remove` is broken on a vanilla provisioned file** —
    it deletes custom functions before the connector layout whose web viewer
    calc references them, hits `in_use`, and rolls back ("Nothing was removed
    — the file is exactly as it was"). Transactional and safe, but 0.4.0
    cannot uninstall its own components. (Apply/reconcile are fine.)
40. **[fm] HTML deploy works over the schema lane.** The deployed app lives in
    `persistentData` (key `ADT`, instance = app name) beside ADT's provenance
    stamps (originId/runId/versions — what reconcile compares).
    `update:persistentData` upserts a 430KB HTML bundle fine, verified by
    fresh read. No handshake, no connector, lock-proof, hosted-file-capable:
    `adt deploy`'s plugin-lane requirement is a convenience, not a necessity.
41. **[fm] Rename ripples correctly and preserves data** — `update:table
    newName` kept rows, kept id, auto-renamed the same-named occurrence, and
    FileMaker rewrote dependent calc TEXT (refs are by id). Diff consequence:
    compare calc text only after applying renames, or diff the id graph.
42. **[fm] The clone/rebuild pipeline works** (dump → generated ops → new
    file): 4 dependency rules learned — folder trees need parent paths
    reconstructed from nesting; calc fields defer past the relations batch
    AND past calc fields they reference (fixpoint, not one pass); scripts
    topo-sort by Perform Script callees; `removeObjects` takes `[{"id":n}]`
    objects, not bare ints. Result: 100% catalog-count parity incl. long
    script bodies and ownerId provenance (ADT's components status recognizes
    a replayed file, flagging only drift).
43. **[env] fm requires full access for EVERYTHING** — confirmed live: a
    [Data Entry Only] account authenticates then gets DBError 207 on the
    schema lock, even for reads. Client-engagement doctrine: request a
    full-access account or don't bring fm.
44. **[app] pnpm hardening policies bite twice** — after trust-downgrade
    (quirk 24), `blockExoticSubdeps` also blocked a second `adt app add`'s
    install (tailwindcss via @tailwindcss/vite). Workspace .npmrc overrides
    both without touching global policy.
45. **[fm] `Perform Find` can't carry criteria via fm.** The step exposes only
    the `restore` flag — no request/criteria specification. To author a find in
    a script, use Enter Find Mode (22) → Set Field → Perform Find (28). Same
    class as File Options (quirk 34): some GUI-authored specifics aren't in the
    fm surface.
46. **[proc] The MCP-free workflow is proven end-to-end** (connector NOT
    running, `/bridgeStatus` empty): schema read, a 3-table JOIN+GROUP BY data
    read (ExecuteSQL via evaluate), a native-layout screenshot (FM Lens),
    and a local-file data WRITE (fm-authored Set Field script triggered by fmp
    URL, verified by fm read) all succeed with no MCP connector open. The
    connector is avoidable for the entire loop; the only in-Pro execution
    needed (local write) is a triggered fm-authored script, not the MCP.
47. **[env] Dropbox serves version-skewed copies of a live `.fmp12`.** Across
    quit/reopen cycles, Pro opened DIFFERENT sync states of the same file: an
    object verified on disk via a fresh `fm` read was absent from Pro's next
    reopened copy, while an offline edit appeared — objects blinking in and
    out nondeterministically. A clone rebuilt OUTSIDE Dropbox rendered with
    perfect fidelity. **Doctrine: never do active .fmp12 layout/schema work on
    a file inside Dropbox — move it out (or pause sync) first.** Quirk 38 was
    the first symptom of the same hazard. Corollary: re-test any layout-render
    observation on a clean non-Dropbox file before trusting it.
48. **[env] A separate, reproducible render anomaly exists besides Dropbox
    skew:** on the explored layouts, plain buttons placed at top-right
    (y≈14, x>440) did not render in FileMaker Pro, while an identical button
    at bottom-left rendered — verified on a clean non-Dropbox file with fresh
    opens and a fresh file path; the objects are on disk (pure-disk fm read
    confirms), in a clear zone. Root cause unresolved. **Actionable:** place
    agent-added nav where it provably renders (bottom band) until root-caused,
    and treat any single render observation with suspicion — confirm on a
    clean non-Dropbox file.
49. *(machine-local env note in the master list — which physical copy of the
    working file is live on that machine; not portable, omitted here.)*
50. **[fm] `update:script` `edits` validate against the read body, not
    sequentially** — inserting at an index past the original end refuses
    (`edit_path_not_found`). For appends, replace the whole `body`.
51. **[fm] Tri-state switch keys take `true`/`false`, not `1`/`0`** — e.g.
    `Set Error Capture` / `Allow User Abort` `"on": true`; numeric forms are
    refused with `slot_kind_conflict`.
52. **[trigger] An fmp URL naming a script the served file lacks raises a
    modal "This script cannot be found or has been deleted."** — one dialog
    per attempt, each wedging idle/external triggering until a human clicks
    OK (health reports idleState "unsafe"). Verify the script exists in the
    SERVED file (fmnet read), and never spray-and-pray fmp URLs. SOP: agent
    scripts start with Set Error Capture [On] + Allow User Abort [Off] and
    log Get(LastError) somewhere readable.
53. **[bridge] Unauthenticated POST /callScript is silently dropped** — empty
    response, no lastScriptStart recorded in /health. Script starts over the
    bridge only work through the authorized MCP session.
54. **[clipboard] FileMaker's Mac clipboard flavors are the legacy
    `CorePasteboardFlavorType 0x<hex-of-fourchar>` types** (e.g. XMSS =
    0x584D5353), which macOS bridges to `dyn.ah62d4rv4g…` UTIs. The
    deprecated `UTTypeCreatePreferredIdentifierForTag(kUTTagClassOSType,…)`
    returns a SHORT dyn form FileMaker does not read — Paste stays greyed.
    Write/read the CorePasteboardFlavorType string; payload is plain UTF-8
    fmxmlsnippet XML, no declaration, no length prefix.
55. **[helper] A modal dialog starves FileMaker's plug-in idle loop** — the
    FM Lens command channel goes silent during a wedge and drains queued
    commands on dismissal. Live wedge signal: `GET :1366/health` idleState
    "unsafe" (the bridge's HTTP thread keeps answering). Sheets do NOT starve
    idle and appear live in `FMLens_State.sheetsOn`.
