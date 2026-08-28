# pm — DataCraft Project-Management Plugin

Claude Code plugin that packages Joe's project-management layer. **Read
[`WORKFLOW.md`](./WORKFLOW.md) first** — it's the stage chain (Discover →
Chart → Spec → Ticket → Build → Verify → Ship → Learn), which skill owns each
stage, and the one rule: `docs/` is shared record, `_pm/` is personal log. pm
fits around Matt Pocock's skill set; it is the discovery on-ramp and the
session layer, nothing more.

Provides:

- **`/pm:pm-scaffold <name>`** — stands up a project from the bundled
  starter: a client engagement (`Acme` → `datacraft-Acme/`), a personal
  project (`self HomeLab` → plain `HomeLab/`), or `here` to add `_pm/` to an
  existing folder. The starter is **minimal by design** — day-one files only
  (`CLAUDE.md`, `docs/intent/`, `docs/adr/`, `_pm/` with skeleton and
  sessions); every other folder is documented in the stamped `CLAUDE.md`'s
  taxonomy table and created on first write, never pre-built. Runs the
  skeleton interview, ensures a git repo, wires the tracker pointer (0.10.0).
- **`discovery`** skill — the stage before planning: a loose conversational
  riff to find the shape and intent of a piece of work, written to
  `docs/intent/<slug>.md` with a size call (one session → build it;
  multi-session → `/wayfinder` with the intent attached).
- **`whats-next`** skill — morning open: reads intents, the tracker frontier,
  and recent sessions; proposes a pick-up; drafts the day's Intent block into
  a per-person session file; claims the ticket.
- **`checkpoint`** skill — mid-session re-aim at a consequential result:
  appends a dated re-aim under the Intent (append-only — earlier re-aims
  stay), pushes the change into the affected tickets.
- **`stepping-away`** skill — end-of-day close: compares Intent to what
  shipped, writes the session entry, settles the tracker, routes durable
  knowledge to shared libraries.
- **`verify-before-done`** skill — evidence before claims: run the
  verification fresh, read the output, report claim + evidence together.
  Ships the `## Verifying your work` block the template carries (and
  pm-scaffold stamps in-place), so the floor holds without the plugin.
- **`okf`** skill *(utility, outside the stage chain)* — format contract for
  the opt-in `knowledge/` bundle: OKF conventions, sprout tripwires,
  boundaries.
- **`granola-transcript`** skill *(utility, outside the stage chain)* —
  fetches full verbatim Granola meeting transcripts (list-then-match; the
  notes.granola.ai link id is not the meeting id) and lands them in
  gitignored `_pm/transcripts/`.
- **`credential-guard` hook** — the one deterministic guardrail: a
  `PreToolUse` hook on Bash that blocks `git add` / `git stage` /
  `git commit` when a credential-shaped file would be staged or committed —
  including compound chains, directory operands, and quoted `-C` paths
  (hardened 0.10.0; regression tests in
  [`hooks/test-credential-guard.sh`](./hooks/test-credential-guard.sh)).
  Examples/templates (`*.example`, `*.sample`) pass.

> Upgrading a project scaffolded by pm ≤ 0.9? See
> [`MIGRATION-0.8.md`](./MIGRATION-0.8.md) — it covers the ≤ 0.7 files
> (`TASKS.md`, `_pm/decisions/`, `context-map.md`) and the 0.10 changes
> (dashboard removed; template now current). The `dashboard` skill was
> deleted in 0.10.0; `design-handoff` and `html-artifacts` moved to the
> **design-dc** plugin in 0.5.0.

## Install

```
/plugin marketplace add datacraftdevelopment/dc-plugins
/plugin install pm
```

After install, `/pm:pm-scaffold` and the bundled skills are available in
every session on that machine.

## Use

```
/pm:pm-scaffold Acme
```

Creates `datacraft-Acme/` in the current directory, ready to work.

## Layout

This plugin lives in the `pm/` subfolder of the [`dc-plugins`](../)
marketplace:

```
pm/
├── .claude-plugin/
│   └── plugin.json          ← plugin manifest (marketplace.json is one level up)
├── commands/
│   └── pm-scaffold.md       ← /pm:pm-scaffold
├── hooks/
│   ├── hooks.json · credential-guard.sh · test-credential-guard.sh
├── skills/
│   ├── discovery/ · whats-next/ · checkpoint/ · stepping-away/
│   ├── verify-before-done/ · okf/ · granola-transcript/
└── template/                ← the minimal starter /pm:pm-scaffold copies
```

## Updating

**This repo is the design home** — the DC-Project-Builder mirror was retired
2026-08-28 (`docs/intent/pm-010-lightening.md`); edit `template/` directly.
Edit `commands/pm-scaffold.md` to change what the command does; edit
`skills/` to change the day-to-day workflow. Bump `version` in
`plugin.json`, commit, push — machines pick it up on
`/plugin marketplace update dc-plugins`. Run
`bash hooks/test-credential-guard.sh` after touching the hook.
