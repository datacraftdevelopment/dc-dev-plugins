# pm — DataCraft Project-Management Plugin

Claude Code plugin that packages Joe's project-management starter. Provides:

- **`/pm:pm-scaffold <name>`** — stands up a project from the starter: a client engagement (`Acme` → `datacraft-Acme/`), a personal project (`self HomeLab` → plain `HomeLab/`), or `here` to add `_pm/` to an existing folder. Renames the placeholder and runs the skeleton interview either way.
- **`whats-next`** skill — morning open: reads project memory, proposes a pick-up, drafts the day's Intent block.
- **`stepping-away`** skill — end-of-day close: compares Intent to what shipped, writes the session entry, updates TASKS.
- **`design-handoff`** skill — writes a lean brief for pasting into Claude Design (data-driven or concept-driven).
- **`html-artifacts`** skill — produces rich editorial HTML artifacts (plans, brainstorms, status reports) instead of long markdown.
- **`okf`** skill — reference card for the opt-in `knowledge/` bundle: OKF format conventions, sprout tripwires, boundaries.

## Install

```
/plugin marketplace add datacraftdevelopment/dc-plugins
/plugin install pm
```

After install, `/pm:pm-scaffold` and the bundled skills are available in every session on that machine.

## Use

```
/pm:pm-scaffold Acme
```

Creates `datacraft-Acme/` in the current directory, ready to work.

## Layout

This plugin lives in the `pm/` subfolder of the [`dc-plugins`](../) marketplace:

```
pm/
├── .claude-plugin/
│   └── plugin.json          ← plugin manifest (marketplace.json is one level up)
├── commands/
│   └── pm-scaffold.md       ← /pm:pm-scaffold
├── skills/
│   ├── whats-next/
│   ├── stepping-away/
│   ├── design-handoff/
│   ├── html-artifacts/
│   └── okf/
└── template/                ← the starter /pm:pm-scaffold copies — mirrored from DC-Project-Builder
```

## Updating

The scaffold itself evolves in the **DC-Project-Builder** repo (`datacraftdevelopment/dc-project-builder`) — the design home, where the `docs/_design/` history lives. Changes land there first, then get mirrored into `template/`; only the template's `CLAUDE.md` and `README.md` intentionally differ (stamped-project voice, no design history, no local skills). Verify a sync with `diff -rq <builder> template/`.

Edit `commands/pm-scaffold.md` to change what the command does; edit `skills/` to change the day-to-day workflow. Bump `version` in `plugin.json`, commit, push — machines pick it up on `/plugin marketplace update dc-plugins`.
