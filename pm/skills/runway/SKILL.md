---
name: runway
description: Set up and run Runway, the factory loop that works a repo's ready tickets unattended, from either Linear or GitHub Issues (one tracker per repo, chosen in runway.json). Use when the user wants to start a new factory project, point a repo at Linear or GitHub for Runway, label tickets for Runway, write a repo's worker-env.md, check what Runway is doing or waiting on, answer a decision packet, schedule, pause, resume or stop the loop, check quiet-time rules, or run a retro on its runs.
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

1. **Tracker.** Linear: create the project in Joe's team (or confirm the one he
   named). GitHub: confirm the repo (`owner/name`) and that Joe's `gh` is signed in.
2. **Point the repo at it.** If Joe wants Matt's interactive setup
   (`/setup-matt-pocock-skills`, which only he can type), run it first, then
   `setup.sh`: it keeps Matt's `triage-labels.md`, `domain.md` and Agent skills
   block and rewrites `issue-tracker.md` with Runway's gating rule. Re-running
   `setup.sh` after Matt's setup restores that rule. Without Matt's setup,
   `setup.sh` seeds all three docs itself.
   Linear: `bash "${CLAUDE_PLUGIN_ROOT}/runway/setup.sh" <repo> <TEAM-KEY> "<project name>"`.
   GitHub: `bash "${CLAUDE_PLUGIN_ROOT}/runway/setup.sh" <repo> --github [owner/name]`
   (the repo defaults to the clone's github.com origin).
   Either writes `docs/agents/issue-tracker.md` (the labels and gating rule below),
   `triage-labels.md` and `domain.md` when missing, a `runway.json` and an "Agent
   skills" section in `CLAUDE.md` (Matt's three sub-blocks), then commits.
   The GitHub doc keeps Matt's GitHub conventions as they are and adds Runway's
   labels and gating rule. Edit `runway.json` before the first run: `check_cmd`
   must be the repo's real test command, and `agent_cmd`'s `--allowedTools`
   must allow it.
3. **Labels.** `RUNWAY setup` for Linear checks the key (Mac keychain service
   `runway-linear`), the team and the project. For GitHub it checks `gh` auth,
   the repo and that Issues is on. Both create Runway's labels when they're
   missing and never recolor existing ones; GitHub also creates Matt's five triage labels. On GitHub it also warns when the
   repo is public: issues and Runway's comments are public then, so no client
   names, credentials or NDA material.
4. **Worker environment.** Copy `${CLAUDE_PLUGIN_ROOT}/runway/worker-env.md`
   to `docs/agents/worker-env.md` and fill it in from the repo: what a fresh
   worktree lacks, the verify command, paths to leave alone. Every ticket run
   reads it first. Commit it.
5. **Plan.** `/to-spec`, then `/to-tickets`, published to the repo's tracker
   (the Linear project or the GitHub repo).
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
  `blocked_by`, `claimed_by`, `errored`; `paused`; `machine`). `errored` is the
  kind of the ticket's latest attempt that didn't merge (`agent-failed`,
  `no-commits`, `check-failed`, `merge-conflict`, `signed-out`) or null; flag
  those tickets and offer `RUNWAY discuss <ticket>`. Prefer it over plain
  `RUNWAY status`, and summarize it for Joe as running, next, blocked and
  waiting on him (read each waiting ticket's `packet`).
- "What is it doing right now" comes from the heartbeat, `<repo>/_pm/runway-state.json`:
  `phase` (`sync|prep|agent|check|merge|finish|idle|stopped`, plus `paused` and
  `waiting` with a `reason`), `ticket`, `attempt`, `since`, `last_result`. A
  non-idle phase only counts as live if its `pid` is still running; otherwise
  it's a crash's leftovers, so say so.
- `RUNWAY tick` runs one step; `RUNWAY loop` runs until nothing is ready.
- `bash .../schedule.sh status|run|uninstall <repo>`: the scheduled job.
- The log is `<repo>/_pm/runway.log`; each agent call is in `_pm/runway-runs.jsonl`. The row with `kind: outcome` ends a ticket: `result` is `done|needs-human|stopped|signed-out`, and `outcome` is the finer kind (`merged|question|agent-failed|no-commits|check-failed|merge-conflict|stopped|signed-out`).
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

### The verdict and `"merge"`

After the fix pass and the final check, a judge step (read-only, built from the
triage rules above) gives the round `pass` or `fail`, with blocking and
non-blocking findings and each done ticket's acceptance criteria mapped to
evidence. Rules: a red check after the last edit is always `fail`; a criterion
with no evidence is blocking; a judge that returns nothing parseable is `fail`,
never `pass`; a finding both seats raise is blocking unless the judge shows it
wrong. A batch is marked `hold` when the PR body's merge danger says one-way (or
says nothing clear) or any ticket was gated `needs-human`: it can pass review but
never auto-merges.

The verdict lands in `_pm/runway-review.md`, as a `verdict` row in
`_pm/runway-runs.jsonl` (with the reviewed SHA), and as the first line of the PR
body (`Review: FAIL, 2 blocking findings`, `Review: PASS (would merge)`).

`"merge"` in `runway.json` says what the verdict is for:

- `off` (default): the verdict is only recorded.
- `shadow`: recorded, and a pass reads "would merge" so Joe can compare it with
  his own call before trusting it.
- `on_pass`: reserved for auto-merge. Nothing merges yet.

With `shadow` or `on_pass` there is no in-finish fix pass. A `fail` verdict files a
ticket through the tracker (`Fix review findings on runway/integration (round N)`,
label `ready-for-agent`) with the blocking findings, the failing check output and
`Refs` lines. The queue builds it, it merges into integration, and the next finish
reviews the new head. `"review_rounds": 2` (default) allows the first review plus
one re-review; if the re-review fails, the fix ticket is parked `needs-human` with
both reviews and nothing new is filed. A repeat fail on the same head, check and
findings comments on the open fix ticket instead. Round count and fix-ticket id live
in `_pm/runway-finish.json`; a new non-fix ticket merging starts a new batch. `off`
keeps the fix pass.

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

## Sign-ins

Before a tick claims a ticket, preps a packet or starts the finish step, Runway
runs status commands (never a model call): `claude auth status` (Codex:
`codex login status`), `gh auth status` when a draft PR will be opened, the
Linear key on a Linear project, and both review seats when `review` is `panel`.
Idle ticks check nothing. If one fails, nothing is claimed, the heartbeat goes
to `waiting` with a reason like "Claude Code needs signing in (`claude auth
login`)", the log says the same and one notification goes out until it clears.
The app shows that reason like a quiet-time reason. `RUNWAY machine` and
`status --json` (`signin`) list each check's result. Joe signs in; the next tick
checks again. A status command can say "logged in" while the token refresh is
already dead (unverified whether `claude auth status` catches it), so the rule
behind it stands: the first agent call that fails on auth pauses the loop.

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
- **Default model.** The templates pin `claude-sonnet-5-5` (the exact ID, not an
  alias) on `agent_cmd`, `prep_cmd` and `review_cmd`; the fix pass and PR body
  inherit it. Opus is opt-in per ticket through the `opus` profile: label a
  ticket `harness:opus` (or `Harness: opus`) when it needs architecture
  judgment. It costs about twice as much per token, so don't make it the
  default.
- **Which model answered.** Every agent record in `_pm/runway-runs.jsonl` has a
  `model` field, read from the JSON result's `modelUsage` (null when the harness
  doesn't report it), so `runway retro` can compare models.
- **Revisit the default** if `runway retro` shows Sonnet tickets retrying or
  parking more than about 1 in 5.
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

`RUNWAY discuss <ticket>` opens an interactive `claude` in the repo root to talk
a ticket through. It takes a waiting ticket (packet or parked) or an errored one
(`errored` in `status --json`, including a ticket still being retried), writes
its brief to `_pm/discuss/<id>.md`, and starts claude on that file. Anything
else exits non-zero and starts nothing. `RUNWAY discuss --loop` is for the loop
itself and always runs: `_pm/discuss/loop.md`. It is always the claude harness,
whatever the ticket's harness. The brief carries trusted authors' comments only.

## Talk a ticket through

You were started by `RUNWAY discuss` with a brief in `_pm/discuss/`. Read it
first, then talk it through with Joe in plain words. Casual and short.

**Decision packet.** Explain the choice and read the code the options touch.
Sort the open questions with pm's fast-grill buckets: technical questions go to
Astra through Ringer's grill-review kit as one task; one-way doors, taste, and
anything contradicting what Joe already said come to Joe. With a single
question, skip the seat and walk it.

**Parked or errored ticket.** Say what went wrong and why, from the log, the
check output and the transcript. Then lay out the ways out: do the blocked step
with Joe now, change the ticket, fix the cause (a flaky check, a missing tool in
the worker env), or drop it.

**Loop in error.** Say what state the loop is in and why (stale heartbeat, a
failed tick, a failed sign-in check, a failed finish), and the way out: restart
the job, sign in again, clear a stale lock. Installing or removing LaunchAgents
is Joe's step: give him the command, don't run it.

Rules for all three:

- Post `RUNWAY go|no <ticket> "<note>"` only after Joe says go or no on this
  ticket in this session, with his own words as the note. Never on a
  recommendation alone.
- Read-only on the repo unless Joe asks for a change. A change made with him
  goes on a branch, never straight onto main.

On GitHub only a trusted author's comment counts as Joe's: the repo's OWNER,
MEMBER or COLLABORATOR. A `go` or `drop` from anyone else is ignored (and logged
once in `_pm/runway.log`), and a stranger's comments never reach the agent's
ticket text. `gh` writes as Joe's account, so the same rule holds: post a go only
after Joe said go on that ticket.

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
ticket with an unknown harness label instead of crashing the tick. 0.5.0 sets a repo up for GitHub Issues:
`setup.sh --github`, a GitHub tracker doc, and `RUNWAY setup` for GitHub (auth, repo,
Issues, labels, public-repo warning). The GitHub adapter itself landed in 0.4.5 to 0.4.9. 0.5.10 updates the docs and
descriptions to say Runway works either Linear or GitHub, one tracker per repo, chosen in `runway.json`.

## Review coverage and retry safety

A merge verdict requires an explicit Acceptance or Acceptance criteria section with Markdown bullets in
each completed ticket's original body. Runway derives stable ticket/criterion IDs from the complete text,
then requires the judge to cover each exactly once with evidence. Missing, ambiguous, changed, duplicate
or unknown coverage fails the round. The verdict record preserves both expected and supplied inventories.

Parking writes a shared trusted operation intent before changing labels or state, then a completion marker.
Every Mac reconciles unfinished intents before approving or selecting work. Retry a parked ticket with a
fresh `go` comment after completion. Merely removing needs-human or re-adding go cannot prove when approval
happened, so it no longer enables retries after a shared park. Initial approvals and stop/release behavior
remain unchanged. Closed GitHub fix tickets reopen only after their spent approval is cleared under this
barrier. Historical comments may be paged to locate the last barrier, even for unclaimed tickets.
