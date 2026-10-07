# dc-dev-plugins

Datacraft's plugins for **Claude Code and Codex**. The `pm/`, `design-dc/`,
`fm-dc/`, `ui-test/`, and `basecamp-dc/` folders are the shared source. Claude Code installs them from
`.claude-plugin/marketplace.json`; the Codex builder creates compatible editions
from the same tracked files. See [Codex installation and compatibility](docs/codex.md).

## What this repo assumes: Ringer

These plugins are written for Joe's stack, and that stack runs **Ringer** — the
verified-swarm delegation tool. Every delegated model call goes through it; none
of the skills here dispatch Codex or a second Claude inline. It is a hard
prerequisite for `pm`, and the workflow that drives `fm-dc` and `design-dc`
sessions inherits it.

What assumes it:

- `pm/WORKFLOW.md` — Joe's binding of the SDLC; names Ringer as installed.
- `pm` skill `fast-grill` — sends each grilling round's technical bucket to the
  Astra seat as one Ringer task (kit `_Core/Ringer/local/templates/grill-review/`).
- PM's `orchestrate` — prepares shared setup and dispatches ready worker nodes
  through Ringer, up to six active subagents under meaningful outcome tickets.
  `build-swarm` can execute a prepared real ticket frontier in worktree waves.
- `cross-review-gate` — an explicitly needed two-seat review runs through Ringer;
  PM's conditional schedule owns when to use it.
- `ui-test` skill `ui-test` — the UI runner (Codex computer-use) and its
  verifier are both Ringer tasks; also needs a one-time Codex computer-use
  approval per target app (see `ui-test/README.md`).

Where it lives (none of it ships in this repo):

| Piece | Location |
|---|---|
| Ringer itself | stock upstream clone at `~/Agentic-Mini/_Core/Ringer` (moved out of Dropbox 2026-09-12); `ringer` on PATH is a shim to its `ringer.py`; `RINGER_ROOT` overrides the path |
| `ringer`, `cross-review-gate`, `build-swarm` skills | `_Core/library/skills/agent-operations/`, symlinked into `~/.claude/skills/` (that is why they are not plugin skills — they live with their transport) |
| live config, worker shims, kits | the private `datacraftdevelopment/desk` repo |
| Codex edition | `python3 scripts/install_ringer.py --install` packages the same skills for Codex (`scripts/ringer_bridge.py` finds the clone) |

A machine without Ringer can still install the plugins, but `fast-grill` runs
`(unseated)`, the build loop and the review gate cannot dispatch, and
`WORKFLOW.md` is the wrong document — read `pm/SDLC.md` instead.

## Install in Codex

From this checkout, with Python 3, Git, and the Codex CLI installed:

```bash
python3 -m pip install -r scripts/requirements-codex.txt
python3 scripts/build_codex.py --install
```

This installs all five plugins into your personal Codex marketplace. Start a new
Codex task to load them. Use the same command after updating the source plugins.
The installer uses Codex's bundled `plugin-creator` helpers; see the guide if your
installation stores them elsewhere. For a build without installation, omit `--install`.

Add/update the **Ringer** and **cross-review-gate** skills from the canonical
shared library, using the existing Ringer clone and its configured workers:

```bash
python3 scripts/install_ringer.py --install
```

Use `--source <agent-operations-directory>` if the library is in a different
location. To refresh only PM, use `python3 scripts/build_codex.py --plugin pm --install`.

Install or refresh the two **Claris ADT plugins** from Claude's active installations:

```bash
python3 scripts/install_claris.py --install
```

Run this after Claude updates its Claris plugins, then open a new Codex task.
The adapter reads Claude's installed-plugin registry, preserves Claris's originals,
and generates local Codex packages with the ADT MCP server. See the compatibility
guide for update behavior and standards-pack selection.

## Install in Claude Code

Add the marketplace once, then install whichever plugins you want:

```
/plugin marketplace add datacraftdevelopment/dc-dev-plugins
/plugin install pm
```

Update everything later with:

```
/plugin marketplace update dc-dev-plugins
```

## Plugins

| Plugin | Command / skills | What it does |
|---|---|---|
| **pm** | `/pm:pm-scaffold`, `whats-next`, `orchestrate`, `stepping-away`, `session-succession` (beta), `okf` | Outcome-sized tickets, one orchestrator, up to six subagents working a dependency graph, proportionate verification and concise handoffs. See [`pm/README.md`](pm/README.md). |
| **design-dc** | `design-handoff`, `html-artifacts`, `excalidraw-artifacts`, `design-sync` | Design handoffs and artifacts. Direct DesignSync requires a host that exposes that tool. |
| **ui-test** | `ui-test` | macOS UI runner and independent verifier through Ringer, with decoded PNG evidence and explicit PASS/FAIL/BLOCKED outcomes. See [`ui-test/README.md`](ui-test/README.md). |
| **fm-dc** | `/fm-init` · `fm-scaffold` · `fm-status` · `fm-rollback` · `fm-docs-sync`; skills `fm-core`, `fm-scripts`, `fm-xml`, `fm-saxml`, `fm-patch`, `fm-dataapi`, `fm-odata`, `fm-connections`, `fm-docs`, `baseelements`, `mbs` | Agentic FileMaker development — SaXML patching with verify/rollback, schema analysis, snippet validation, turnkey direct OData + Data API connection tool-skills, BaseElements + MBS. Needs system `python3` + `lxml` and Claris CLI tools. See [`fm-dc/README.md`](fm-dc/README.md). |
| **basecamp-dc** | `bc-client-face`, `bc-close-out`; session-start hook | Basecamp as the client face, opt-in per repo via `.basecamp/config.json` — inert without it, never a `pm` dependency. Conventions + quirk-safe shipping on top of the official basecamp CLI and its `/basecamp` skill. See [`basecamp-dc/README.md`](basecamp-dc/README.md). |
| **sdlc** | `gate-hooks`, `review-policy`; agent `policy-reviewer` | Repo-level enforcement kits: gate hooks installed into a repo's `.claude/` (production gate, protected paths, test lock) and a `REVIEW.md` policy with a read-only reviewer. Claude Code only: no Codex edition, no `pm` or Ringer dependency. See [`sdlc/README.md`](sdlc/README.md). |

### Not a plugin: `factory/`

[`factory/`](factory/README.md) holds the software-factory research and the Runway experiments, plus the factory site (`factory/site/`). It isn't listed in `marketplace.json` and none of the `make-*.sh` cuts or Codex builds ship it.

## Adding a new plugin

1. Create a subfolder `<plugin-name>/` with its own `.claude-plugin/plugin.json`.
2. Add a line to `.claude-plugin/marketplace.json` pointing `source` at `./<plugin-name>`.
3. Commit and push.
4. On each machine: `/plugin marketplace update dc-dev-plugins` then `/plugin install <plugin-name>`.

No new marketplace is ever needed — this repo is the single marketplace for everything.

## Layout

```
dc-dev-plugins/
├── .claude-plugin/
│   └── marketplace.json     ← lists every plugin
├── pm/                      ← plugin: project management
│   ├── .claude-plugin/plugin.json
│   ├── commands/            ← /pm:pm-scaffold
│   ├── skills/              ← whats-next, stepping-away, design-handoff, html-artifacts, okf
│   └── template/            ← the starter /pm:pm-scaffold copies (mirrored from DC-Project-Builder)
├── fm-dc/                   ← plugin: agentic FileMaker development
    ├── .claude-plugin/plugin.json
    ├── commands/            ← /fm-init, fm-scaffold, fm-status, ...
    ├── agents/              ← fm-patch-builder, fm-xml-validator
    ├── skills/              ← ddr, fm-patch, fm-xml, fm-connections, ...
    ├── tools/               ← Python tooling (ddr, patch, fmlint, docs)
    └── templates/           ← what /fm-scaffold copies
└── basecamp-dc/             ← plugin: Basecamp client face (opt-in per repo)
    ├── .claude-plugin/plugin.json
    ├── skills/              ← bc-client-face, bc-close-out
    ├── hooks/               ← session-start (silent without .basecamp/config.json)
    └── scripts/             ← bc_config.py, doc_roundtrip.py
```

### Complete local Codex refresh

`python3 scripts/refresh_codex.py --install` refreshes all seven local packages
and connects the shared library and PM workflow skills. Use `--check` for a
read-only connection report. See [Codex setup](docs/codex.md).
