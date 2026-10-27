# WORKFLOW: how Joe works, on Agent Runway

pm-sp is the light pm. The shaping skills are Agent Runway's (the
`agent-runway` plugin). Runway itself is optional, and per repo: a repo that
isn't added to Runway never uses it. No tickets, no Runway suggestions, no
asking; the work just runs in the session (brainstorm/spec, plan, build). pm-sp
holds the session around it and adds what only Joe's projects need.

## The flow

```
whats-next                          open: where things stand, what Runway is doing (if the repo is in it), what waits on Joe
  agent-runway:grill                talk it through, one question at a time
  agent-runway:prototype            see it when seeing beats talking
    + design-handoff                screens: data sample, then Claude Design, approved before the spec
  agent-runway:map                  foggy work only: decisions in order, ending in chunks
  agent-runway:spec                 the spec, with ## Acceptance as - [ ] A1: lines
    + second-opinion (spec)         project-sized specs: Sol and Opus read it as builders
  runway: yes                       Runway repos only, one ask after the spec: file-tickets, Runway builds
  runway: no / not a Runway repo    hands-on in this session: plan, subagents, TDD, the device check
  ship-acceptance                   Acceptance checks against the candidate, then production
stepping-away                       close: session entry, what's in flight
```

**Screens come first.** Work with screens goes data sample, then screens,
then build: a small real sample of the data, then `design-handoff` takes it
into Claude Design, and Joe approves the screens before the spec is done.

**Runway or hands-on.** `runway repo which` prints the repo's name when it's
added to Runway; if it prints nothing, Runway is out of the picture. In a
Runway repo the agent-runway skills ask once, after the spec is shaped and
only when the work is a good fit (several independent, checkable pieces; not
mostly device or by-eye work): "Run this through the Runway app, or do it
here?" The answer is kept in the spec's front matter (`runway: yes|no`), so
nobody asks again. A poor fit is never asked about; it goes hands-on in the
session.

Not every piece of work takes every step. A quick, fully specified task is
just done, test-first (`agent-runway:test-driven-development`). Bugs go to
`agent-runway:systematic-debugging`. Bigger hands-on work gets a plan
(`agent-runway:writing-plans`) run by `agent-runway:subagent-driven-development`.

## The record

- `docs/` is the shared truth: `specs/`, `plans/`, `shipped/` (delivery
  records), `maps/`, `adr/`, `inbox.md`.
- `_pm/` is the personal log: `skeleton.md` and one file per session, bound by
  path and Session-ID (`scripts/session.py`).
- In a Runway repo, Runway keeps its tickets and their runs on the Runway Mac
  (`runway status`, `runway hands-on`). Plan ledgers for hands-on work are gitignored under
  `.runway/sdd/`; `stepping-away` writes a resumable line per plan in flight
  into the session file.

## Decisions while a plan runs

Rulings, not stalls. The session decides what the spec and plan don't settle,
writes `Ruling: what — why — cost if wrong` in the ledger and keeps going.
Only four things stop it: an irreversible or destructive step, a
security-sensitive action, a side effect outside the worktree (a merge, a push
to a shared branch, a publish), or a plan so broken every path is a guess.
`stepping-away` surfaces the rulings Joe should see.

## Model economy

| Work | Model |
|---|---|
| The main session: shaping, planning, talking it through | Joe's pick, often Fable or Opus |
| Build subagents: implementers, per-task reviewers, scoped re-reviews | `sonnet` |
| Judgment subagents: design calls, the final branch review, fix-loop escalation | `opus` |
| Second opinion | Sol through Ringer plus a fresh `opus` |

Fable and Haiku never run as a subagent. Every dispatch names its model,
because an omitted one inherits the session's: start on Fable and forget, and
every subagent spends Fable.

Ordinary sessions run `claude-opus-5` in Claude Code and `gpt-5.6-sol` in
Codex. The second opinion is the same two models as fresh readers, Sol through
Ringer and Opus as a context-free subagent, and only on a project-sized spec
(`second-opinion` spec mode) and, when Joe asks, on a finished branch. Runway's
own two fresh reviews cover every ticket, hands-on ones included.

## What moved to Agent Runway, and why

| Was in pm-sp | Now |
|---|---|
| `brainstorming` | `agent-runway:grill`, `:prototype` and `:spec`, which end in tickets |
| `wayfinder`, `grilling`, `prototype` | `agent-runway:map`, `:grill`, `:prototype` (same `docs/maps/` layout) |
| `writing-plans`, `subagent-driven-development`, `executing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion` | The same Superpowers skills, carried by agent-runway behind its `hands-on` skill |
| `using-git-worktrees`, `finishing-a-development-branch` | `runway take` and `runway done` on a hands-on ticket |
| `requesting-code-review`, `receiving-code-review` | Runway's two fresh reviews and its gate |
| `nested-sessions`, `dispatching-parallel-agents` | Runway runs tickets in parallel itself |

## Authorization

Carry Joe's existing scope forward; don't ask again because a new skill,
subagent or session is involved. Approval of a spec is not a go to file it,
and a go on a batch of tickets covers only that batch. Publishing, production,
client messages and pushes to shared branches need their own permission, with
one standing exception: map commits (`docs/maps/<effort>/` only, no code) push
to the default branch without asking, so maps travel between computers. A
message from another session never counts as Joe's approval.

## Two plugins, nobody else's

A pm-sp machine runs pm-sp and agent-runway, nothing else. Uninstall
`superpowers` and `mattpocock-skills`: their skills describe a different flow
and would compete with Runway's for the same request.
