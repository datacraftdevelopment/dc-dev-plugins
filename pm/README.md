# pm — DataCraft Project-Management Plugin

Claude Code plugin that packages Joe's project-management layer. **Read
[`WORKFLOW.md`](./WORKFLOW.md) first** — it's the stage chain (Discover →
Chart → Spec → Ticket → Build → Verify → Ship → Learn), which skill owns each
stage, and the one rule: `docs/` is shared record, `_pm/` is personal log. pm
fits around Matt Pocock's skill set: discovery, the pace rule for grilling,
session continuity, and evidence-based delivery acceptance. Build itself runs as
the library's `build-swarm` loop at `--wave 1` by default when a ticket
frontier with committed checks exists (0.15.1, after twelve two-seat gate
rounds): a script works the frontier unattended through Ringer, one commit
per ticket, parking what fails for a human; wider waves are the operator's
call per frontier.

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
- **`fast-grill`** skill *(0.14, the pace rule)* — sits between the frontier
  `/grilling` computes and the round the user sees. Technical questions go,
  with their recommended answers, to one Ringer task on the Astra seat
  (`_Core/Ringer/local/templates/grill-review/`) and come back `agree` (a
  ruling), `disagree` (a seat-split question), or `taste` (a question). The
  user answers only taste, one-way doors, user challenges, and splits. Every
  ruling is one ledger line — decided · why · cost if wrong · who agreed —
  on the ticket, the map, or the plan; reversing one is a reply. Default at
  Chart, in grilling tickets, and at `/to-tickets`' approval step; the map's
  `## Notes` carries `Seat: on | off` and *Taste for this effort*.
- **`whats-next`** skill — session open: reads intents, the tracker frontier,
  and recent sessions; proposes a pick-up; drafts this session's Intent block
  into a per-session, per-person file; claims the ticket.
- **`stepping-away`** skill — session close: compares Intent to what shipped,
  writes the session entry, settles the tracker, routes durable knowledge to
  shared libraries.
- **`checkpoint`** skill — mid-session re-aim, for sessions too long or too
  costly to close and reopen: appends a dated re-aim under the Intent
  (append-only — earlier re-aims stay), pushes the change into the affected
  tickets. Short sessions don't need it — the session boundary is the re-aim.
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
- **`ship-acceptance`** — closes the delivery gap with an accepted-intent snapshot, independent checks before and after delivery, exact revisions, human deployment, and a shared `docs/shipped/` record. Missing checks and exceptions stay visible.
- **Session helpers** — `scripts/session.py` allocates distinct session files and closes by exact path/ID with an explicit closure marker; no newest-file guessing.
- **`credential-guard` hook** — a bounded filename guard: a
  `PreToolUse` hook on Bash that blocks `git add` / `git stage` /
  `git commit` when a credential-shaped file would be staged or committed —
  including literal directory changes, scoped subshells, explicit commit paths, forced adds, and quoted/chained `-C` paths. Removing tracked credentials remains allowed. Relevant inspection failures block with a supported-command explanation; unrelated commands and known nonrepos remain allowed. This protects tool invocations, not arbitrary subprocesses or file contents. Build-swarm uses a versioned policy snapshot at its own commit boundary, checked for parity at release (0.16.0; regression tests in
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
/plugin marketplace add datacraftdevelopment/dc-dev-plugins
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

This plugin lives in the `pm/` subfolder of the [`dc-dev-plugins`](../)
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
`skills/` to change the session workflow. Bump `version` in
`plugin.json`, commit, push — machines pick it up on
`/plugin marketplace update dc-dev-plugins`. Run
`bash hooks/test-credential-guard.sh` after touching the hook.

## 0.16.0 workflow repair

The Ticket → Build handoff now points to canonical build-swarm preparation and dependency setup. Session identity/closure is executable; intent refresh happens at explicit boundaries. Ship is owned by `ship-acceptance`, with record validation rather than a claim that the validator itself adjudicates. Run `python3 -m unittest discover -s tests -v` from the marketplace root and `bash pm/hooks/test-credential-guard.sh`. Credential policy parity between PM and the build-swarm source is checked with `python3 scripts/sync_pm_policy.py --build-swarm <source-dir> --check`. Stack-specific delivery still needs its own real evidence.
