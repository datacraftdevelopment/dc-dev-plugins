---
name: runway
description: Set up and run Runway, the factory loop that works a Linear project's ready tickets unattended. Use when the user wants to start a new factory project, point a repo at Linear for Runway, label tickets for Runway, write a repo's worker-env.md, check what Runway is doing or waiting on, answer a decision packet, schedule or stop the loop, or run a retro on its runs.
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

- `RUNWAY status`: what's waiting on Joe, running, ready, blocked and done.
- `RUNWAY tick` runs one step; `RUNWAY loop` runs until nothing is ready.
- `bash .../schedule.sh status|run|uninstall <repo>`: the scheduled job.
- The log is `<repo>/_pm/runway.log`; each agent call is in `_pm/runway-runs.jsonl`.
- `RUNWAY finish` forces the finish step; its PR body lands in `_pm/runway-pr.md`.

Closing a chat never pauses the loop, and nothing here should say it does.
Stop it with `schedule.sh uninstall`, and say it's stopped only once
`schedule.sh status` shows it unloaded.

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
