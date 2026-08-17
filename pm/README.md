# pm — DataCraft Project-Management Plugin

Claude Code plugin that packages Joe's project-management starter. Provides:

- **`/pm:pm-scaffold <name>`** — stands up a project from the starter: a client engagement (`Acme` → `datacraft-Acme/`), a personal project (`self HomeLab` → plain `HomeLab/`), or `here` to add `_pm/` to an existing folder. Renames the placeholder, runs the skeleton interview, and seeds `_pm/context-map.md` (including a standing row per shared library the machine's global instructions name) either way.
- **`whats-next`** skill — morning open: reads project memory, proposes a pick-up, drafts the day's Intent block.
- **`checkpoint`** skill — mid-session re-aim at a consequential result: dated re-aim under the Intent, TASKS updated, context map touched only if a source changed.
- **`stepping-away`** skill — end-of-day close: compares Intent to what shipped, writes the session entry, updates TASKS, and routes durable knowledge to any shared libraries the machine's global instructions name.
- **`okf`** skill — reference card for the opt-in `knowledge/` bundle: OKF format conventions, sprout tripwires, boundaries.
- **`brainstorm-lite`** skill — one-session planning for small, low-fog work: short interview, 2-3 approaches, an approved design written to `_pm/decisions/` before any code. Foggy multi-session work routes to a wayfinder map instead; composes with Matt Pocock's `/grilling`, `/tdd`, `/implement`. Replaces superpowers brainstorming in a Matt-primary stack (added in 0.6.0).
- **`verify-before-done`** skill — evidence before claims: run the verification fresh, read the output, report claim + evidence together. Gates "done"/"fixed"/"passing", task completion, and checkpoint / stepping-away entries (added in 0.6.0).

> `design-handoff` and `html-artifacts` moved to the **design-dc** plugin (this marketplace) in pm 0.5.0 — install `design-dc@dc-plugins` alongside pm to keep them.

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
│   ├── checkpoint/
│   ├── stepping-away/
│   ├── okf/
│   ├── brainstorm-lite/
│   └── verify-before-done/
└── template/                ← the starter /pm:pm-scaffold copies — mirrored from DC-Project-Builder
```

## Updating

The scaffold itself evolves in the **DC-Project-Builder** repo (`datacraftdevelopment/dc-project-builder`) — the design home, where the `docs/_design/` history lives. Changes land there first, then get mirrored into `template/`; only the template's `CLAUDE.md` and `README.md` intentionally differ (stamped-project voice, no design history, no local skills). Verify a sync with `diff -rq <builder> template/`.

Edit `commands/pm-scaffold.md` to change what the command does; edit `skills/` to change the day-to-day workflow. Bump `version` in `plugin.json`, commit, push — machines pick it up on `/plugin marketplace update dc-plugins`.
