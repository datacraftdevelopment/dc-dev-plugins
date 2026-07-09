# dc-plugins

Datacraft's Claude Code plugin marketplace. One repo, added once per machine, hosting all of Joe's plugins. Each plugin lives in its own subfolder; `.claude-plugin/marketplace.json` lists them.

## Install

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
| **pm** | `/pm-scaffold`, `whats-next`, `stepping-away`, `design-handoff`, `html-artifacts` | Scaffolds a client engagement from the datacraft starter and runs the day-to-day PM + delivery workflow. See [`pm/README.md`](pm/README.md). |
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
│   ├── commands/            ← /pm-scaffold
│   ├── skills/              ← whats-next, stepping-away, design-handoff, html-artifacts
│   └── template/            ← the starter /pm-scaffold copies
└── fm-dc/                   ← plugin: agentic FileMaker development
    ├── .claude-plugin/plugin.json
    ├── commands/            ← /fm-init, fm-scaffold, fm-status, ...
    ├── agents/              ← fm-patch-builder, fm-xml-validator
    ├── skills/              ← ddr, fm-patch, fm-xml, fm-connections, ...
    ├── tools/               ← Python tooling (ddr, patch, fmlint, docs)
    └── templates/           ← what /fm-scaffold copies
```
