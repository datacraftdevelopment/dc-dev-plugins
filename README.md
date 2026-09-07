# dc-plugins

Datacraft's plugins for **Claude Code and Codex**. The `pm/`, `design-dc/`, and
`fm-dc/` folders are the shared source. Claude Code installs them from
`.claude-plugin/marketplace.json`; the Codex builder creates compatible editions
from the same tracked files. See [Codex installation and compatibility](docs/codex.md).

## Install in Codex

From this checkout, with Python 3, Git, and the Codex CLI installed:

```bash
python3 -m pip install -r scripts/requirements-codex.txt
python3 scripts/build_codex.py --install
```

This installs all three plugins into your personal Codex marketplace. Start a new
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
/plugin marketplace add datacraftdevelopment/dc-plugins
/plugin install pm
```

Update everything later with:

```
/plugin marketplace update dc-plugins
```

## Plugins

| Plugin | Command / skills | What it does |
|---|---|---|
| **pm** | `/pm:pm-scaffold`, `whats-next`, `stepping-away`, `design-handoff`, `html-artifacts`, `okf` | Scaffolds a client engagement, personal project, or in-place `_pm/` from the datacraft starter and runs the day-to-day PM + delivery workflow. See [`pm/README.md`](pm/README.md). |
| **design-dc** | `design-handoff`, `html-artifacts`, `excalidraw-artifacts`, `design-sync` | Design handoffs and artifacts. Direct DesignSync requires a host that exposes that tool. |
| **fm-dc** | `/fm-init` · `fm-scaffold` · `fm-status` · `fm-rollback` · `fm-docs-sync`; skills `fm-core`, `fm-scripts`, `fm-xml`, `fm-saxml`, `fm-patch`, `fm-dataapi`, `fm-odata`, `fm-connections`, `fm-proofkit`, `fm-docs`, `baseelements`, `mbs` | Agentic FileMaker development — SaXML patching with verify/rollback, schema analysis, snippet validation, turnkey direct OData + Data API connection tool-skills, ProofKit doctrine, BaseElements + MBS. Needs system `python3` + `lxml` and Claris CLI tools. See [`fm-dc/README.md`](fm-dc/README.md). |

## Adding a new plugin

1. Create a subfolder `<plugin-name>/` with its own `.claude-plugin/plugin.json`.
2. Add a line to `.claude-plugin/marketplace.json` pointing `source` at `./<plugin-name>`.
3. Commit and push.
4. On each machine: `/plugin marketplace update dc-plugins` then `/plugin install <plugin-name>`.

No new marketplace is ever needed — this repo is the single marketplace for everything.

## Layout

```
dc-plugins/
├── .claude-plugin/
│   └── marketplace.json     ← lists every plugin
├── pm/                      ← plugin: project management
│   ├── .claude-plugin/plugin.json
│   ├── commands/            ← /pm:pm-scaffold
│   ├── skills/              ← whats-next, stepping-away, design-handoff, html-artifacts, okf
│   └── template/            ← the starter /pm:pm-scaffold copies (mirrored from DC-Project-Builder)
└── fm-dc/                   ← plugin: agentic FileMaker development
    ├── .claude-plugin/plugin.json
    ├── commands/            ← /fm-init, fm-scaffold, fm-status, ...
    ├── agents/              ← fm-patch-builder, fm-xml-validator
    ├── skills/              ← ddr, fm-patch, fm-xml, fm-connections, ...
    ├── tools/               ← Python tooling (ddr, patch, fmlint, docs)
    └── templates/           ← what /fm-scaffold copies
```

### Complete local Codex refresh

`python3 scripts/refresh_codex.py --install` refreshes all seven local packages
and connects the shared library and PM workflow skills. Use `--check` for a
read-only connection report. See [Codex setup](docs/codex.md).
