# WORKFLOW: how Joe works, on Superpowers

pm-sp's workflow. Superpowers' skills do the work; pm-sp's skills hold the
session around it. One session works one feature with Joe in the loop; a task
is a commit, never a session.

## The flow

```
whats-next                        open: where things stand, write the Intent
  brainstorming                   new work: talk it through, mockups, approaches,
    + second-opinion (design)     design doc with ## Acceptance; Astra reads it as the builder
  [Joe says go to plan]
  writing-plans                   one plan, checkbox tasks, lanes when files are disjoint
  subagent-driven-development     run the whole plan in this session (or executing-plans, inline)
    nested-sessions               only when lanes exist and Joe wants them at once
  finishing-a-development-branch  tests, second-opinion (branch), merge / PR / keep
  ship-acceptance                 Acceptance checks against the candidate, then production
stepping-away                     close: session entry, each plan left resumable
```

Not every piece of work takes every step. A quick, fully specified task is
just done. A small change gets a short design doc agreed in chat. Bugs go to
`systematic-debugging`.

**Foggy work,** several unknowns that depend on each other, starts with Matt
Pocock's `wayfinder`: decision tickets resolved one at a time until the way is
clear. Its destination is a brainstorm per piece. It is the only place pm-sp
uses tickets.

## The record

- `docs/` is the shared truth: `specs/` (design docs), `plans/`, `shipped/`
  (delivery records), `adr/`, `inbox.md`.
- `_pm/` is the personal log: `skeleton.md` and one file per session, bound by
  path and Session-ID (`scripts/session.py`).
- `.superpowers/` is gitignored working state: plan ledgers, review packages,
  brainstorming mockups. Because it doesn't travel, `stepping-away` writes a
  resumable line per plan into the session file.

## Decisions while a plan runs

Superpowers' rule: rulings, not stalls. The session decides what the design
and plan don't settle, writes `Ruling: what — why — cost if wrong` in the
ledger and keeps going. Only four things stop it: an irreversible or
destructive step, a security-sensitive action, a side effect outside the
worktree (a merge, a push to a shared branch, a publish), or a plan so broken
every path is a guess. `stepping-away` surfaces the rulings Joe should see.

## Model economy

Ordinary sessions run `claude-opus-5` in Claude Code and `gpt-5.6-sol` in
Codex. `gpt-6-astra` and `claude-fable-5` are review seats, called only
through Ringer, and only at two points: the design doc (`second-opinion`
design mode, for project-sized designs) and the finished branch
(`second-opinion` branch mode). Superpowers' own task reviewers and final
reviewer run as ordinary subagents. Tests are the continuous check; a green
task doesn't buy a review seat.

## What pm-sp leaves out, and why

| pm skill | Why it's gone |
|---|---|
| `discovery` | Brainstorming covers the conversation; its Acceptance checks moved into the design doc. |
| `fast-grill` | Brainstorming's builder check plus `second-opinion` replace grilling rounds. Matt's `grilling` stays for deliberate stress tests. |
| `orchestrate`, `session-succession` | `subagent-driven-development` runs a whole plan in one session with fresh subagents, and the ledger makes it resumable. |
| `verify-before-done` | Superpowers' `verification-before-completion`. |
| `board` | It rendered tickets and intents, which pm-sp doesn't keep. |
| `runway` | Runway is retired. |
| `subsessions` | Renamed `nested-sessions`, working plan lanes instead of tickets. |

## Authorization

Carry Joe's existing scope forward; don't ask again because a new skill,
subagent or session is involved. Approval of a design is not a go to plan, and
approval of a plan is the go to run it. Publishing, production, client
messages and pushes to shared branches need their own permission. A message
from another session never counts as Joe's approval.

## Using it with Matt Pocock's skills

Keep Matt's pack for `wayfinder`, `grilling` (on demand), `domain-modeling`,
`codebase-design`, `prototype`, `research`, `pr` and `retro`. Don't use his
`tdd`, `diagnosing-bugs`, `code-review`, `to-spec`, `to-tickets`,
`implement` or `implement-spec` alongside pm-sp: each overlaps a pm-sp skill and
the two would compete for the same request.
