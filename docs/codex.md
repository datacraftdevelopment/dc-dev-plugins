# Claude Code and Codex compatibility

Maintain the five shared plugin folders once. Claude Code reads them directly;
`scripts/build_codex.py` generates Codex packages. Do not edit the generated copies.
The source Claude manifests, commands, skills, agents, and hooks stay intact.

## Installation and updates

For the complete setup, use one command from this checkout:

```bash
python3 scripts/refresh_codex.py --install
```

This refreshes PM, design, FileMaker, UI testing, Basecamp, Ringer, Claris, and `dc-workflow`, then
connects managed instruction blocks in the shared library and Codex's global
`AGENTS.md`. It preserves text outside those blocks and backs up existing
instructions before the first change. It does not pull repositories, update
Claude plugins, run models, change credentials, or trust hooks.

Use `python3 scripts/refresh_codex.py --check` for a read-only connection report.
It compares installed source metadata with the active Claude versions and reports
stale or missing links. Owned plugins also record their source version and a
fingerprint of tracked source contents, executable permissions, and the Codex
builder. Changed source or an older package without this metadata requires a
refresh; untracked local files are ignored. Optional live services are reported separately.
Without either flag, it builds a preview under `.codex-build/`. All packages build in staging and validate before any live package is replaced.
A failed copy restores previous directories. Codex registration remains sequential:
a registration failure is reported and may leave installed caches at mixed versions;
rerun the refresh after resolving it. A partial run is never reported complete.

The original per-plugin commands below remain available.

```bash
python3 -m pip install -r scripts/requirements-codex.txt
python3 scripts/build_codex.py --install
```

Run this from a Git checkout. The builder reads the current contents of tracked
files, including edits, but excludes untracked/ignored files and rejects symlinks.
Add new source files to Git's index before building. This prevents local virtual
environments, sandbox databases, personal tracking, and client files entering a
package. The `fm-lens` plugin (formerly `fm-adt-helper`) is intentionally outside this build; its source moved to the private FM_Agent_Lens repo (`lens/`) on 2026-09-16.

Installation builds owned packages in `~/plugins/{pm,design-dc,fm-dc,ui-test,basecamp-dc}`, validates
them with Codex's plugin-creator helper, registers them in
`~/.agents/plugins/marketplace.json`, and runs `codex plugin add` for each.
Unrelated package folders are never overwritten. Existing generated folders are
replaced, so keep all edits in this repository. Updates use the helper's version
cachebuster and reinstall flow. Open a **new Codex task** after installation.

The helper default is `~/.codex/skills/.system/plugin-creator`. If your Codex
installation provides it elsewhere, pass `--plugin-creator-dir <path>`.
If the helper is missing, the builder still works without `--install`; install
or update Codex's plugin-creator skill before using the installation option.

Build without changing Codex settings:

```bash
python3 scripts/build_codex.py
python3 scripts/build_codex.py --output /tmp/dc-codex-preview
```

The default output is `.codex-build/` (ignored by Git). These are private local
plugins, not submissions to the public OpenAI plugin store.

## What is adapted

| Feature | Claude Code | Codex edition |
|---|---|---|
| Plugin manifests | Original `.claude-plugin/plugin.json` | Generated `.codex-plugin/plugin.json` with interface metadata |
| Existing skills | Original files | Normalized frontmatter and Codex runtime guidance |
| Slash commands | `commands/*.md` | Named `skills/<command>/SKILL.md` entrypoints |
| FileMaker agents | Native Claude agent definitions | Builder and validator skills; delegate via available Codex subagent tools |
| Bundled tools | `${CLAUDE_PLUGIN_ROOT}` | `PLUGIN_ROOT` resolved from the loaded skill's absolute location |
| Scaffold instructions | `CLAUDE.md` | `AGENTS.md` in generated templates and scaffold procedures |
| PM credential guard | Claude `PreToolUse` hook | Codex `Bash` hook, same guard script and event payload |
| Session succession beta | Capability-checked native session controls | Codex task creation/status/archive guidance, with queued IDs distinguished from running acknowledgement |
| DesignSync | Requires the native tool | Capability check; local inventory/diff/handoff when unavailable |

Try these in a new Codex task: “Use pm-scaffold here,” “Use whats-next,”
“Use fm-status,” or “Use design-handoff.” The skill picker also exposes the
converted commands by their names. The builder reports the skill count for each
package, including converted commands and agent procedures.

### UI testing and Basecamp

`ui-test` uses the existing Ringer runner/verifier flow from either host. Install
its Python dependencies from `ui-test/requirements.txt` in the Python runtime
used by the checks. Computer-use availability and target-app approvals belong to
the actual worker environment; a successful package build does not establish them.

`basecamp-dc` requires the Basecamp CLI and its `basecamp` skill for live actions.
It stays inactive in projects without `.basecamp/config.json`. Follow its setup
instructions to add the optional `docs/agents/client-face.md` contract; installation
does not opt a project into client updates. Existing project files are preserved.
The SessionStart hook accepts Codex's working-directory payload and the Claude
environment. Codex supports the `CLAUDE_PLUGIN_ROOT` compatibility variable in
plugin hooks; review and trust the hook in `/hooks` before relying on startup context.

## Dependencies and limits

### Claris ADT plugins

```bash
python3 scripts/install_claris.py --install
```

This installs local Codex editions of `filemaker-agentic-development` and
`adt-standards-default` into the personal marketplace. Claude's
`~/.claude/plugins/installed_plugins.json` selects the **active user installation**
of each `@claris` plugin. The adapter checks its manifest version and path against
the supplied cache; it does not pick the highest version directory or fall back
to an old cache when the registry is missing or ambiguous.

Use this same command after Claude updates the Claris plugins. **Refreshing is
manual; no watcher or scheduled job is installed.** Open a new Codex task after
every refresh so the skill descriptions and MCP tools reload together. A changed
Claude integration surface (for example, new hooks or commands) stops the adapter
for review instead of silently dropping it.

The output preserves Claris's binaries, references, authorship, and copyright.
Only Codex manifests, skill host instructions, and the standards-pack entrypoint
are generated. Cache process markers and filesystem junk are omitted. No Claris
content is copied into `fm-dc` or committed to this repository; generated packages
are local adaptations, not an independently maintained or publicly distributed fork.

The ADT MCP server runs the generated package's `bin/adt mcp` with Claris's
`FM_HTTP_BASE_URL=http://127.0.0.1:1366`. Its executable path is generated for this
machine. Codex recognizes it as `adt-mcp`. The CLI wrappers retain their existing
dependency on the user's installed ADT application resources and FileMaker Pro.
Bundled CLI commands can be run by full path or with the plugin's `bin/` prepended
to that shell's PATH. No global CLI shim or FileMaker project is changed.

The standards plugin is discoverable as `adt-standards-default`, but its pack slug
is **`default`**. A project opts in with `"standards": { "pack": "default" }` in
`adt.json`; installing the plugin alone does not change conventions. `adt standards`
resolves the pack through the existing Claris installation. Project overrides,
per-file enablement, and advisory-only review rules still apply.

For a preview, omit `--install` (output: `.codex-build/`) or pass `--output <dir>`.
Use `--cache <claris-cache-dir>` and `--registry <installed_plugins.json>` only when
Claude stores its installations elsewhere. The generated metadata records the
source version and path. Missing sources and unrelated output folders fail without
overwriting them.

Validation on the initial 0.5.0 import: plugin schema checks, source-preservation
and update-selection tests, CLI version, default-pack path resolution, and an MCP
initialize/tools-list handshake. The server advertised seven tools. No database
queries or mutations were used as installation tests.

### Shared library and PM workflow dependencies

`python3 scripts/install_workflow.py --install` installs `dc-workflow`: the
`library` router, `build-swarm`, the 25 skills declared by Claude's active
Matt Pocock package, and `dc-setup`. Sources are selected from the active user
installation in Claude's registry; a version mismatch or missing PM skill stops
the build. These are short Codex entry points that read the canonical skills
and their resources in place, not copied knowledge or copied loop scripts.

Library content and script edits are available immediately. Refresh after a
Claude plugin update changes the Matt Pocock cache path or its skill catalog.
Local source paths belong to generated packages; they are not redistributable
plugins. Use `--library` and `--registry` if their locations differ.

The library's new `AGENTS.md` points to its shared `CLAUDE.md`. Synchronization
checks Git status first, pulls only a clean tree with `--ff-only`, and preserves
existing edits. A lookup never commits someone else's work. Global Codex
instructions provide routing only; they do not impose the library schema on
unrelated repositories. PM `fast-grill` remains the authority for the Fable seat
in Codex, even when a Matt Pocock skill supplies the surrounding procedure.

`build-swarm` keeps its canonical implementation in the library. Its loop defaults
to wave 1 and uses runtime state outside Dropbox. Its `--dry-run` can park and
commit tickets; use a disposable repository for setup tests.

### Ringer and cross-review-gate

`python3 scripts/install_ringer.py --install` installs a separate `ringer` plugin
containing the canonical `ringer` and `cross-review-gate` skills. Their source
remains `_Core/library/skills/agent-operations/` in the adjacent shared library,
also used by Claude Code. Use `--source <directory>` to override that location;
use `--output <directory>` without `--install` to inspect a build. Re-run the
installer after editing either canonical skill. Originals are never rewritten.

The bundled `scripts/ringer_bridge.py` launches the existing clone at
`~/Agentic-Mini/_Core/Ringer`; set environment variable `RINGER_ROOT` if it
moves. It preserves the current working directory and Ringer's normal config
lookup. Config, credentials, worker shims, logs, and history stay in their
existing locations. The bridge's `--print-root` resolves template/doc locations;
other arguments pass through to Ringer unchanged.

PM loads `ringer` before orchestration and `cross-review-gate` at review gates.
The review uses the configured Astra + Fable panel: with a Codex orchestrator,
Claude provides the cross-vendor seat and Codex provides fresh-context review.
Consensus, Hold, artifact-freeze, and dispatch-consent rules are preserved.
Codex-led PM grilling sends the adversarial task to Fable (`engine: claude`,
`model: claude-fable-5`). The Ringer bridge's `--grill-template` emits this variant
with Codex reasoning flags removed. Claude-led grilling retains the original
Astra template. The two-seat cross-review panel remains Astra + Fable.

The `local/templates/adversarial-review-panel/` and `local/templates/grill-review/`
kits remain in the existing Ringer clone. The separate `dc-workflow` package connects `build-swarm` and Matt's workflow skills. CLI validation/dry runs verify routing and manifest parsing. The 2026-09-07 Hello World bakeoff additionally verified live Astra and Fable execution: both passed on their first attempt.

### Other dependencies

- The credential hook must be reviewed/trusted in Codex's `/hooks` interface
  before it runs. Installation does not automatically trust it. No bypass is set.
- Ringer, Granola, the separate Claude Design bridge, shared knowledge libraries,
  and other external skills remain dependencies; installing these packages does
  not install or authenticate those services. Skills check availability first.
- A Codex review seat invoked from Codex is independent but is not cross-vendor.
- FileMaker tooling still needs its Python dependencies, Claris tools, and any
  required server access. See `fm-dc/requirements.txt` and `fm-dc/README.md`.
- This is a local Codex integration. It does not emulate Claude's native DesignSync
  or register Claude agent model aliases as Codex model names.

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_codex.py
bash .codex-build/pm/hooks/test-credential-guard.sh
```

The build tests cover source preservation, command/agent discovery, template
instructions, portable dependencies, and refusal to replace unrelated folders.
Run the FileMaker test suite from `.codex-build/fm-dc` using an environment with
`fm-dc/requirements.txt` installed; live E2E cases additionally need Claris tools
and a prepared sandbox. Package validation runs before every installation.

Implementation follows OpenAI's [Claude plugin migration guidance](https://developers.openai.com/plugins/guides/submit-claude-plugin)
for commands, agents, and skills, and its [Codex hook contract](https://developers.openai.com/codex/hooks)
for local hook discovery, event compatibility, and trust.

## Verified local setup — 2026-09-07

All seven personal plugins are enabled. Codex discovery finds all 28 `dc-workflow`
entrypoints without personal-plugin loading errors. A disposable PM project passed
a Fable technical grill, an Astra build-swarm ticket with red proof and automatic
patch integration/closure, and an Astra + Fable review. The review identified four
local diagnostic/update issues, fixed with regression tests. The panel's first
Astra report retried because the test harness lacked the local alias to its shared
validator; the alias now points to the unchanged upstream check.

The existing computer-use MCP command used a stale relative path; the local config
now points at the bundled executable. Its initialize/tools-list check advertised
10 tools; ProofKit advertised 18. Pencil's missing executable entry is disabled
with its configuration preserved. These machine-specific changes have a local
config backup and are not reapplied by refresh.

The credential guard passed 18 script checks and was approved individually through
Codex's `/hooks` review UI. A separate app-server `hooks/list` check confirms
`pm@personal`, `preToolUse`, matcher `Bash`, `enabled: true`, and `trustStatus: trusted`.
No hook-trust bypass was enabled. Recheck trust after plugin updates.

The disposable FileMaker project is `~/.ringer/jobs/filemaker-connection-smoke/`.
Its `CodexConnectionSmoke.fmp12` was created with the `fm` CLI, registered in
`adt.json`, and its `ConnectionSmoke` table reread successfully in a fresh process
with a closing summary and `rolledBack: false`. ADT provisioning then succeeded;
a fresh `adt components status` found all 43 components present, no blockers, and
no drift. No client database was used.

FileMaker Pro Agent's ADT service is reachable on port 1366, and the generated
Codex ADT MCP package successfully initializes and lists tools. The final live
file read is **not yet verified**. The disposable file was opened through Finder,
but ADT's automatic connector start did not complete. `adt doctor --file` reports
an open, unshared local file (DBError 803 during its script inspection) and no
completed plugin handshake. The previously completed fresh-process checks prove
that the required connector scripts are installed.

FileMaker UI inspection crashes or times out. Three installed FileMaker versions
also share the same application identifier; target Pro Agent by its full path.
The scratch project's `Start ADT Connector.webloc` attempts Claris's documented
`fmp26://$/CodexConnectionSmoke?script=Connect%20To%20ADT` URL, but did not establish
the handshake either. Because both Pro 26 installations register that scheme,
its destination is not guaranteed to be the Agent application. See
[Claris's URL documentation](https://help.claris.com/en/pro-help/content/opening-files-url.html).

To finish, run **Connect To ADT** in the open `CodexConnectionSmoke` file in
FileMaker Pro Agent and leave its connector window open. This manual fallback is
needed because ADT's automatic start failed. Then run:

```bash
cd ~/.ringer/jobs/filemaker-connection-smoke
~/plugins/filemaker-agentic-development/bin/adt doctor --json --file CodexConnectionSmoke
```

Follow with `connectedFiles` and a `table_metadata` read for that exact file. Do
not treat `doctor`'s overall `ready` status alone as proof of the live data path:
inspect its individual handshake checks. Saved results are in the disposable
project's `connection-evidence.json`, `components-status.json`, and
`doctor-file-latest.json`. No database sharing or account privileges were changed.

Claude Design and Granola remain optional, unverified host connections.

## Local Claude Code installation

PM 0.19 uses one orchestrator and outcome-sized tickets, with up to six bounded
subagents executing ready nodes of a work graph. `whats-next` reaches the new
`orchestrate` skill automatically for implementation; worker assignments do not
become extra tickets. Existing project requirements remain binding. Manual
`stepping-away` → fresh session → `whats-next` is still the default.
The optional `session-succession` beta is not enabled by installation. Its tests
verify local state transitions and recovery; they do not prove click-free native
startup or memory release. Test those separately on the actual host.

The private shared source and the public `dc-plugins` marketplace are different
release surfaces. For local development, register this checkout through Claude's
supported marketplace CLI and install its named private editions:

```bash
claude plugin marketplace add .
claude plugin install pm@dc-dev-plugins --scope user
claude plugin install design-dc@dc-dev-plugins --scope user
claude plugin install fm-dc@dc-dev-plugins --scope user
claude plugin install ui-test@dc-dev-plugins --scope user
claude plugin install basecamp-dc@dc-dev-plugins --scope user
```

Run this from the source checkout. After later version bumps, use
`claude plugin marketplace update dc-dev-plugins` and `claude plugin update
<name>@dc-dev-plugins --scope user`. Verify the installed cache's manifest and
source contents, then remove any superseded installation of the same named plugin
from the public marketplace. Preserve the user's enabled/disabled preference.
Keep the public marketplace if unrelated plugins still use it. Do not hand-edit
Claude's cache or publish private sources to the public tree. Restart Claude Code
after a refresh.

Canonical Ringer and build-swarm skills remain in the shared library. Claude's
existing skill links consume those sources; the Codex refresh packages Ringer's
tracked skill resources and links build-swarm to its canonical implementation.
No client project is opted into a new execution policy merely by installation.
