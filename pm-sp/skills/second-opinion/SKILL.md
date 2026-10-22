---
name: second-opinion
description: "A model from another vendor (Astra, through Ringer) reads a design doc as its builder or reviews a finished branch, so no plan or merge rests on one model approving its own work. Use from brainstorming's builder check, from finishing-a-development-branch, when the repo's CLAUDE.md asks for a cross-model review, or when the user says \"second opinion\", \"get Astra on this\" or \"cross-review\"."
---

# Second opinion

One Ringer task to the cross-vendor seat, at the two points where a second pair
of eyes pays: before a design becomes a plan, and before a branch merges. Not
per task, not per green test run. The plan's own tests and Superpowers' own
reviewers stay the continuous layer; this is the different-vendor check on top.

## The seat

Engine `codex`, model `gpt-6-astra` at medium effort (`gpt-5.6-sol` when Astra
is quota-blocked). Every call goes through Ringer, never an inline Codex call;
the `ringer` skill owns spec, check, engine and watch surface. Ringer runs on
the Mac only, and `ringer` and `codex` resolve only in `zsh -lc`. From a cloud
session, dispatch through Remote Control on the Mac, or say the seat isn't
reachable and continue unseated (below).

The packet is read-only context and the question, nothing else: no transcript,
no unrelated history.

## Design mode

Called from brainstorming's builder check, for a project-sized design doc.

- **Packet:** the design doc's path, the repo path, and the instruction to read
  it as the person who will build it and list what they would still need to ask.
- **Check:** every question has a same-line reason; the seat also flags any
  decision it thinks is hard to reverse (`door:`).
- **Back in brainstorming:** sort its questions with the builder check's into
  the same three piles (answered already, minor, theirs). Doors always go to
  the user's pile. One round, together with the builder check's questions.

## Branch mode

Called from finishing-a-development-branch, or when asked, on a finished branch.

- **Packet:** base and head commits, the diff, the design doc and plan the
  branch answers to, `REVIEW.md` if the repo has one, and the test output at the
  head commit. Use the `cross-review-gate` skill's kit for the mechanics.
- **Verdict:** findings with severity and file:line, each tied to the design,
  the plan or `REVIEW.md`; a finding with no reference is noted, not acted on.
  The seat also checks for a lowered bar: new suppressions, skipped or deleted
  tests, stub implementations, loosened thresholds or check config.
- **After:** fix what it finds in this session (the session keeps its context,
  so it isn't a cold start), rerun the tests, and send the fix once more. A
  second failed review stops: tell the user what's still open and let them
  decide. Never merge past an open finding on your own.

## Unseated

If the task fails with a quota, auth or model-availability error, switch to
Sol once and say so. If Sol fails too, or the user says "no seat this time",
continue without it and mark the result `(unseated)` where the design doc or
the finishing message records it. Never present an unseated result as reviewed.

## What this replaces

pm's `fast-grill`. Grilling rounds are gone from the default flow; brainstorming
asks the questions and its builder check settles the technical ones. Run
Matt Pocock's `grilling` by hand when you want to be stress-tested on purpose.
