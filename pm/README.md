# pm — DataCraft Project-Management Plugin

Claude Code plugin that packages Joe's project-management starter. **Read [`WORKFLOW.md`](./WORKFLOW.md) first** — it's the stage chain (Discover → Chart → Spec → Ticket → Build → Verify → Ship → Learn), which skill owns each stage, and the one rule: `docs/` is shared record, `_pm/` is personal log. pm fits around Matt Pocock's skill set; it is the on-ramp, the session layer, and the visibility layer, nothing more.

Provides:

- **`/pm:pm-scaffold <name>`** — stands up a project from the starter: a client engagement (`Acme` → `datacraft-Acme/`), a personal project (`self HomeLab` → plain `HomeLab/`), or `here` to add `_pm/` to an existing folder. Renames the placeholder, runs the skeleton interview, and seeds `_pm/context-map.md` (including a standing row per shared library the machine's global instructions name) either way.
- **`whats-next`** skill — morning open: reads project memory, proposes a pick-up, drafts the day's Intent block.
- **`checkpoint`** skill — mid-session re-aim at a consequential result: dated re-aim under the Intent, TASKS updated, context map touched only if a source changed.
- **`stepping-away`** skill — end-of-day close: compares Intent to what shipped, writes the session entry, updates TASKS, and routes durable knowledge to any shared libraries the machine's global instructions name.
- **`dashboard`** skill — renders `_pm/dashboard.html`, a self-contained visual status page (today's Intent, wayfinder map with frontier/blocked/fog, tasks, milestones, recent sessions and decisions). Strictly a render of the sources, never a source itself; the template ships in the skill and only its JSON data island gets rewritten. whats-next / checkpoint / stepping-away refresh it automatically, and a staleness badge announces when no ritual has run (added in 0.7.0).
- **`okf`** skill — reference card for the opt-in `knowledge/` bundle: OKF format conventions, sprout tripwires, boundaries.
- **`discovery`** skill — the stage before planning: a loose conversational riff to find the shape and intent of a piece of work, written to `docs/intent/<slug>.md` with a size call (one session → build it; multi-session → `/wayfinder` with the intent attached). Exists because wayfinder's opening grill goes far better fed a shaped intent. Replaces `brainstorm-lite` (0.8.0).
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
│   ├── dashboard/           ← SKILL.md + dashboard-template.html (stamped into _pm/ at runtime)
│   ├── okf/
│   ├── discovery/
│   └── verify-before-done/
└── template/                ← the starter /pm:pm-scaffold copies — mirrored from DC-Project-Builder
```

## Updating

The scaffold itself evolves in the **DC-Project-Builder** repo (`datacraftdevelopment/dc-project-builder`) — the design home, where the `docs/_design/` history lives. Changes land there first, then get mirrored into `template/`; only the template's `CLAUDE.md` and `README.md` intentionally differ (stamped-project voice, no design history, no local skills). Verify a sync with `diff -rq <builder> template/`.

Edit `commands/pm-scaffold.md` to change what the command does; edit `skills/` to change the day-to-day workflow. Bump `version` in `plugin.json`, commit, push — machines pick it up on `/plugin marketplace update dc-plugins`.
