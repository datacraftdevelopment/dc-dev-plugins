---
name: second-opinion
description: "Two fresh readers, Sol (through Ringer) and Opus, read a spec as its builders or review a finished branch, so no batch of tickets or merge rests on the model that wrote it approving its own work. Use on a project-sized spec before it is filed, on a finished branch when asked, when the repo's CLAUDE.md asks for a cross-model review, or when the user says \"second opinion\", \"get Sol on this\" or \"cross-review\"."
---

# Second opinion

Two fresh readers, one from another vendor, at the two points where a second pair
of eyes pays: before a project-sized spec becomes tickets, and before a branch
merges when the user asks. Not per ticket, not per green test run. The tests
and Runway's two fresh reviews on every ticket stay the continuous layer; this
is the different-vendor check on top.

## The readers

Both get the same packet and run at the same time; neither sees the other's
answer.

- **Sol,** the other vendor: one Ringer task, engine `codex`, model
  `gpt-5.6-sol` at medium effort. Every call goes through Ringer, never an
  inline Codex call; the `ringer` skill owns spec, check, engine and watch
  surface. Ringer runs on the Mac only, and `ringer` and `codex` resolve only in
  `zsh -lc`. From a cloud session, dispatch through Remote Control on the Mac,
  or say Sol isn't reachable and continue with Opus alone (below).
- **Opus,** the same vendor with none of this session's context: a fresh
  subagent on `claude-opus-5` (or Ringer's Claude seat when the work is already
  going through Ringer). Fresh is the point: it hasn't watched the spec or the
  code get written.

The packet is read-only context and the question, nothing else: no transcript,
no unrelated history. Merge the two answers before acting: a point both raise
counts once, and a point only one raises is still a point.

## Spec mode

For a project-sized spec, after `agent-runway:spec` writes it and before
the build (or, in a Runway repo with `runway: yes`, before
`agent-runway:file-tickets` files it).

- **Packet:** the spec's path, the repo path, and the instruction to read it as
  the person (or unattended agent) who will build it and list what they would
  still need to ask. Ask them too which Acceptance lines an unattended
  reviewer couldn't prove (those are done hands-on).
- **Check:** every question has a same-line reason; each reader also flags any
  decision it thinks is hard to reverse (`door:`).
- **After:** sort their questions into three piles (answered already, minor,
  the user's). Doors always go to the user's pile. Fix the spec once, one
  round, then go on to the plan (or, in a Runway repo with `runway: yes`, offer `file-tickets`).

## Branch mode

When the user asks, on a finished branch (hands-on work they want read by
another vendor before `runway done`, or a branch outside Runway).

- **Packet:** base and head commits, the diff, the spec and plan the
  branch answers to, `REVIEW.md` if the repo has one, and the test output at the
  head commit. Use the `cross-review-gate` skill's kit for the mechanics.
- **Verdict (each reader):** findings with severity and file:line, each tied to the spec,
  the plan or `REVIEW.md`; a finding with no reference is noted, not acted on.
  Both also check for a lowered bar: new suppressions, skipped or deleted
  tests, stub implementations, loosened thresholds or check config.
- **After:** fix what it finds in this session (the session keeps its context,
  so it isn't a cold start), rerun the tests, and send the fix once more. A
  second failed review stops: tell the user what's still open and let them
  decide. Never merge past an open finding on your own.

## Unseated

If Sol fails with a quota, auth or model-availability error, or Ringer isn't
reachable, retry once, then continue with Opus alone and mark the result
`(Opus only)` where the spec or the closing message records it: one
vendor read it, not two. If both fail, or the user says "no second opinion this
time", mark it `(unseated)`. Never present a one-reader or unseated result as a
full second opinion.

## What this replaces

pm's `fast-grill`. Grilling rounds are gone from the default flow;
`agent-runway:grill` asks the questions while the work is shaped. Run it by
hand when you want to be stress-tested on purpose.
