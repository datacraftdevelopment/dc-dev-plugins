# pm — DataCraft Project-Management Plugin

Claude Code plugin that packages Joe's project-management starter. **Read [`WORKFLOW.md`](./WORKFLOW.md) first** — it's the stage chain (Discover → Chart → Spec → Ticket → Build → Verify → Ship → Learn), which skill owns each stage, and the one rule: `docs/` is shared record, `_pm/` is personal log. pm fits around Matt Pocock's skill set; it is the on-ramp, the session layer, and the visibility layer, nothing more.

Provides:

- **`/pm:pm-scaffold <name>`** — stands up a project from the starter: a client engagement (`Acme` → `datacraft-Acme/`), a personal project (`self HomeLab` → plain `HomeLab/`), or `here` to add `_pm/` to an existing folder. Renames the placeholder, runs the skeleton interview, and seeds `_pm/context-map.md` (including a standing row per shared library the machine's global instructions name) either way.
- **`whats-next`** skill — morning open: reads intents, the tracker frontier, and recent sessions; proposes a pick-up; drafts the day's Intent block into a per-person session file; claims the ticket.
- **`checkpoint`** skill — mid-session re-aim at a consequential result: dated re-aim under the Intent, the change pushed into the affected tickets, superseded decisions archived to `docs/adr/`.
- **`stepping-away`** skill — end-of-day close: compares Intent to what shipped, writes the session entry, settles the tracker (close / comment / unclaim), routes durable knowledge to shared libraries, offers to push the log.
- **`dashboard`** skill — renders `_pm/dashboard.html`, a **local-only stage board**: one stream per `docs/intent/` entry with its stage (Discover → Chart → Spec → Ticket → Build → Verify → Ship → Learn) derived entirely from artifacts — intent status, wayfinder map, spec and tickets on the tracker, merges — plus today's Intent and recent sessions. No human-maintained fields; gitignored; on probation (unused → deleted). whats-next / checkpoint / stepping-away refresh it (stage board in 0.8.0; first version 0.7.0).
- **`okf`** skill — reference card for the opt-in `knowledge/` bundle: OKF format conventions, sprout tripwires, boundaries.
- **`discovery`** skill — the stage before planning: a loose conversational riff to find the shape and intent of a piece of work, written to `docs/intent/<slug>.md` with a size call (one session → build it; multi-session → `/wayfinder` with the intent attached). Exists because wayfinder's opening grill goes far better fed a shaped intent. Replaces `brainstorm-lite` (0.8.0).
- **`verify-before-done`** skill — evidence before claims: run the verification fresh, read the output, report claim + evidence together. Gates "done"/"fixed"/"passing", task completion, and checkpoint / stepping-away entries (added in 0.6.0).

> Upgrading a project from pm ≤ 0.7? See [`MIGRATION-0.8.md`](./MIGRATION-0.8.md) — `TASKS.md`, `_pm/decisions/`, and `context-map.md` are no longer sources of truth.

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
