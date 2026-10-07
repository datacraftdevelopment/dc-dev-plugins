---
name: runway
description: Set up and run Runway, the factory loop that works a Linear project's ready tickets unattended. Use when the user wants to start a new factory project, point a repo at Linear for Runway, label tickets for Runway, write a repo's worker-env.md, check what Runway is doing or waiting on, answer a decision packet, schedule, pause, resume or stop the loop, check quiet-time rules, or run a retro on its runs.
---

# Runway

Runway is a deterministic loop, not an agent. Each tick it preps a decision
packet for every `ready-for-human` ticket on the frontier, runs the next
`ready-for-agent` ticket in its own worktree, checks it, and merges it into
`runway/integration`. When the queue is done it reviews the whole branch, makes
one fix pass and writes a PR body. The base branch is never touched; Joe merges.

The engine is `${CLAUDE_PLUGIN_ROOT}/runway/runway.py` (Python 3.9+ and git,
nothing else). Below, `RUNWAY` means `python3 "${CLAUDE_PLUGIN_ROOT}/runway/runway.py" --root <repo>`.

## Start a factory project

1. **Linear project.** Create it in Joe's team (or confirm the one he named).
2. **Point the repo at it.**
   `bash "${CLAUDE_PLUGIN_ROOT}/runway/setup.sh" <repo> <TEAM-KEY> "<project name>"`
   writes `docs/agents/issue-tracker.md` (the labels and gating rule below),
   a `runway.json` and an "Agent skills" section in `CLAUDE.md`, then commits.
   Edit `runway.json` before the first run: `check_cmd` must be the repo's real
   test command, and `agent_cmd`'s `--allowedTools` must allow it.
3. **Labels.** `RUNWAY setup` checks the Linear key (Mac keychain service
   `runway-linear`), the team and the project, and creates Runway's labels.
4. **Worker environment.** Copy `${CLAUDE_PLUGIN_ROOT}/runway/worker-env.md`
   to `docs/agents/worker-env.md` and fill it in from the repo: what a fresh
   worktree lacks, the verify command, paths to leave alone. Every ticket run
   reads it first. Commit it.
5. **Plan.** `/to-spec`, then `/to-tickets`, published to the Linear project.
   Label each ticket with the gating rule below and add blocks relations for
   the conflict screen.
6. **Schedule.** `bash "${CLAUDE_PLUGIN_ROOT}/runway/schedule.sh" install <repo> [minutes]`
   loads a LaunchAgent that runs the loop (default every 10 minutes). Installing
   it runs on Joe's Mac, so it needs his say-so.

## The gating rule

Sort each ticket into the first bucket that fits:

| Bucket | Label |
|---|---|
| One-way door: live data, deletes, public or production, spend, credentials, client data, an architecture choice that takes more than a session to unwind | `ready-for-human` |
| User challenge: the plan contradicts something Joe said | `ready-for-human`, quoting him |
| Taste: anything a user sees or feels, or what "done enough" means | `ready-for-human` |
| Technical: anything the codebase or the spec can settle | `ready-for-agent` |

Unsure whether something is reversible: it's a door. Unsure between taste and
technical: `ready-for-agent`, with the assumption named in the body. Work under
about an hour isn't its own ticket. The full rule is in each repo's
`docs/agents/issue-tracker.md`.

## Conflict screen

Two tickets that touch the same files (lockfiles, generated code, migrations
and registries count), write the same database or need the same port must not
run side by side. Give them a blocks relation in landing order.

## Running and watching

- `RUNWAY status --json`: the queue as one JSON object (`groups`: waiting,
  running, ready_auto, ready_prep, blocked, done; `tickets` with `packet`,
  `blocked_by`, `claimed_by`; `paused`; `machine`). Prefer it over plain
  `RUNWAY status`, and summarize it for Joe as running, next, blocked and
  waiting on him (read each waiting ticket's `packet`).
- "What is it doing right now" comes from the heartbeat, `<repo>/_pm/runway-state.json`:
  `phase` (`sync|prep|agent|check|merge|finish|idle|stopped`, plus `paused` and
  `waiting` with a `reason`), `ticket`, `attempt`, `since`, `last_result`. A
  non-idle phase only counts as live if its `pid` is still running; otherwise
  it's a crash's leftovers, so say so.
- `RUNWAY tick` runs one step; `RUNWAY loop` runs until nothing is ready.
- `bash .../schedule.sh status|run|uninstall <repo>`: the scheduled job.
- The log is `<repo>/_pm/runway.log`; each agent call is in `_pm/runway-runs.jsonl`.
- `RUNWAY finish` forces the finish step; its PR body lands in `_pm/runway-pr.md`.

Closing a chat never pauses the loop, and nothing here should say it does.
To hold it for a while, pause it (below). To remove it, `schedule.sh uninstall`,
and say it's stopped only once `schedule.sh status` shows it unloaded.

## Review panel

The finish step reviews the whole integration branch. With `"review": "panel"`
(on in `runway.json.template`) it runs two seats through Ringer: a Codex seat and
a Claude seat, reviewing independently. Then one fix pass triages both reports
with no human in the loop:

- A finding both seats raise is agreed: it gets fixed.
- A finding only one seat raises is split: the fixer verifies it against the code
  and judges it. Claude-only findings get extra scrutiny; Codex-only ones are the
  cross-vendor catches.
- Joe is never asked. The fixer ends with a triage table (fixed or skipped, with
  a reason for every skip).

Reports land in `_pm/runway-review-codex.md` and `_pm/runway-review-claude.md`;
the merged findings and triage table go to `_pm/runway-review.md` and into the
PR body (`_pm/runway-pr.md`).

Ringer is optional. Without it, or if neither seat writes a report, Runway logs
the fallback and runs the single Claude review (`"review": "single"`, the engine
default for a `runway.json` that doesn't set it). Cloud sessions can't run the
panel: Codex is blocked there and Ringer is only on the Mac. A cloud thread that
wants an ad hoc panel review starts a Remote Control session on the Mac and runs
`cross-review-gate` there. Factory doesn't ship a `ringer` skill; Joe's library
already has one.

## Pause and resume

A pause is machine-wide (`~/.runway/pause`), holds with the app closed and
leaves the LaunchAgent loaded. Only on Joe's ask:

- `RUNWAY pause --for 1h` or `--until <ISO-8601>`: a running ticket finishes,
  nothing new starts. With neither flag it holds until `resume`.
- `RUNWAY pause --stop-now` also stops the running agent; its ticket goes back
  to ready with a "stopped by pause" comment and keeps its worktree.
- `RUNWAY resume` lifts it.

Say it's paused only after `RUNWAY status --json` shows `paused` set or the
heartbeat phase reads `paused`.

## Quiet time

`RUNWAY machine` prints this Mac's quiet-time rules and whether a tick would run
now, and why not. Show it when Joe asks why nothing is starting (the heartbeat
phase `waiting` carries the same reason). The rules live in
`~/.runway/machine.json` (quiet hours, idle only, not on battery, max agents).
Edit that file only when Joe asks for a specific change, show him the result
with `RUNWAY machine`, and never change it to get a ticket moving. The rules
stop new starts only; a running agent is never touched.

## Harnesses

A harness is the agent CLI that does a ticket's work. The default is Claude
(`agent_cmd`, `prep_cmd` and the rest at the top of `runway.json`).

- `runway.json` `"harness"` sets the project default: `claude` or a key of
  `"harnesses"`.
- `"harnesses"` maps a name to a profile (`agent_cmd`, `prep_cmd`, `review_cmd`,
  `fix_cmd`, `pr_cmd`, `parser`). A profile overlays the top-level commands;
  anything it leaves out falls back to them. Each key must be a profile object;
  keys starting with `_` and non-object values are ignored, so keep notes in a
  top-level `_harness_note`, not inside `"harnesses"`.
- One ticket can override the default: a `harness:<name>` label in Linear, or a
  `Harness: <name>` header in a markdown ticket. An unknown name is logged
  (`park ... unknown harness`) and the ticket is parked as needs-human, not run.
- `RUNWAY status --json` shows each ticket's effective `harness`.
- `RUNWAY whoami` prints this Mac's name, the one stamped on claims
  (`claimed_by`). A ticket claimed by another Mac is skipped here; the claim
  clears when the ticket is parked, paused or retried.

## Decisions

A `ready-for-human` ticket gets a decision packet as a comment (it starts
`🛫 runway`) and the `needs-human` label. Joe approves with a comment starting
`go`, or the `go` label; anything after `go` reaches the agent. **Post a go only
after Joe has said go on that specific ticket, with his choice.** A connector
writes as Joe, so Runway can't tell the difference. `RUNWAY go <ticket> "<note>"`
and `RUNWAY no <ticket> "<note>"` do the same from the command line.

## Retro

`RUNWAY retro` prints usage per ticket and writes `_pm/runway-retro-prompt.md`,
a `/retro` prompt pointing at the runs that struggled. It also asks the retro
to compare what each ticket asked for with what landed. Retros are started by
a human, never scheduled.

## Versions

0.1.0 was the first cut. 0.4.0 adds the two-seat review panel, machine-wide
pause, quiet-time rules and per-project and per-ticket harnesses. No notes were
kept for 0.2 and 0.3. 0.4.1 fixes claim release on Linear, `pause --stop-now`
across repos, and the app's script paths after the engine move. 0.4.2 ignores `_` notes in `"harnesses"` and parks a
ticket with an unknown harness label instead of crashing the tick.
