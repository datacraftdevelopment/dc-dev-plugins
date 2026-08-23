# Intent: pm plugin reshape — fit around the Matt-primary workflow

Author: Joe (DataCraft). Status: accepted. Date: 2026-08-23.
Progress: pm 0.8.0 (discovery, WORKFLOW.md) · 0.9.0 (stage-board dashboard, tracker-first rituals, scaffold wiring, MIGRATION-0.8.md) · 0.9.1 (credential-guard hook, verify-before-done CLAUDE.md block). Remaining: `pm/template/` mirror via the builder. Resolved: `okf` stays in pm; hook lives in pm; verify-before-done stays a skill + ships a block.
Source: discovery session reviewing https://claude.com/blog/the-ai-native-sdlc-playbook against the pm plugin + Matt Pocock's skill set.

## Problem

The working stack has become Matt-primary: `/wayfinder` → grilling → `/to-spec` → `/to-tickets` → `/implement` + `/tdd`. The pm plugin was built before that and now fits around it badly:

- `brainstorm-lite` refuses foggy work and sends it to wayfinder — but the thing actually missing is the stage *before* wayfinder: a loose discovery riff that finds the shape and intent, so wayfinder's breadth-first grill (the heaviest part of Matt's process) starts from something already shaped. brainstorm-lite has never been used for this reason; there was no place it fit.
- Nothing names the stages. Matt's skills are verbs; there is no noun for "where is this project." Everything flows together into one task list and nobody can say what stage the work is at.
- pm keeps its own state (`TASKS.md`, `_pm/decisions/`, `context-map.md`) that competes with the tracker (`GitHub Issues`) and Matt's `docs/adr/` + `CONTEXT.md`. In a team this is a second source of truth.
- The workflow doctrine lives only in the global `Agentic/CLAUDE.md` and in Joe's head. A second machine or second developer installing `pm` gets the parts without the assembly diagram.
- The dashboard renders session notes prettier. That is ceremony; the wayfinder `.scratch/` and GitHub's issue view already show the frontier.

## Proposed outcome

pm becomes exactly three things layered on Matt's engine, and nothing else:

1. **The on-ramp** — `discovery` skill (replaces `brainstorm-lite`): riff back and forth, no ticket discipline, until the shape is visible; writes `docs/intent/<slug>.md` (problem, outcome, affected, constraints, open questions); ends with a size call — one session → just build it; multi-session → `/wayfinder` with the intent attached.
2. **The session layer** — `whats-next` / `checkpoint` / `stepping-away`: per-person, append-only logs in `_pm/`, never authoritative. Session files named per person (`2026-08-23-joe.md`).
3. **The visibility layer** — `dashboard` reshaped into a stage board derived entirely from artifacts (intent exists → Discover; map open → Charting N/M; spec issue → Spec; tickets open → Build; …). Zero human-maintained fields. Rendered file is local-only (gitignored). On probation: if it isn't opened, it gets deleted.

Plus `WORKFLOW.md` shipped in the plugin: the stage table (Discover → Chart → Spec → Ticket → Build → Verify → Ship → Learn), which skill owns each stage, and the one rule — **`docs/` = shared record, `_pm/` = personal log**.

Removed or shrunk: `brainstorm-lite` (replaced), `TASKS.md` (goes, or becomes "what I'm picking up today" inside the session file), `_pm/decisions/` (decisions go to `docs/adr/`), `context-map.md` (suspected ceremony — confirm it has never changed a session's behaviour, then drop). `verify-before-done` stays for now; candidate to fold into a CLAUDE.md block later.

## Affected users and systems

- Joe, solo and multi-agent — daily.
- Future collaborators on DataCraft repos — the team model is: work, pm records the session, push; next person pulls and merges.
- `pm` plugin (`pm/skills/*`, `pm/README.md`, `plugin.json` — breaking, 0.8.0 or 1.0-shaped).
- `pm/template/` — mirrors the external DC-Project-Builder (`datacraftdevelopment/dc-project-builder`); scaffold changes land there first, then get mirrored here.
- `pm-scaffold` — should wire the tracker (run or point at `setup-matt-pocock-skills`) so wayfinder doesn't silently fall back to local markdown.
- `Agentic/CLAUDE.md` "Skill routing" section — shrinks to a pointer at `WORKFLOW.md`.
- Existing projects carrying `_pm/TASKS.md` / `_pm/decisions/` — need a migration note, not a migration.

## Constraints

- Matt's skills are the engine; pm fits around their structure, never the reverse. Anything in pm that is ceremony gets deleted.
- Tracker is GitHub Issues in a team. Intent lives in the repo (`docs/intent/`), not on the tracker.
- Must work for one person + one agent, one person + many agents, and a team.
- Nothing in pm may hold authoritative state that the tracker or `docs/` also holds.
- Skip the playbook's enterprise plays (managed settings, OTel, evals-in-CI, deploy tiers, control-band monitoring) — no payoff at this scale.
- Marketplace pre-flight rules in `CLAUDE.md` apply (no symlinks, no absolute paths, bump version).

## Open questions

- Team sync of `_pm/`: push session files to the branch, or keep `_pm/` out of git entirely and rely on Dropbox / the tracker? "We'll have to play with that."
- Does `verify-before-done` survive as a skill, or become a `## Verifying your work` block in the scaffolded CLAUDE.md?
- Dashboard stage detection for the Learn stage — what artifact marks it? (Playbook: incident → new intent. Candidate: `docs/intent/` entries tagged `source: incident`.)
- Hooks: a `PreToolUse` credential guard (block staging `account.md` / `.env`) is the one deterministic guardrail worth shipping — in pm, or a separate tiny plugin?
- Does `okf` stay in pm or move somewhere orthogonal?

## Size call

Multi-session. Touches five skills, the template mirror in an external repo, the global CLAUDE.md, and has five open questions — chart it with `/wayfinder`, destination: "pm 0.8.0 shipped with discovery, WORKFLOW.md, stage-board dashboard, and the removals; existing projects have a migration note."
