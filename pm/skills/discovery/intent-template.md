# Intent: <short title>

Author: <name>. Status: draft | accepted | superseded. Date: YYYY-MM-DD.
Completion: pending (ship-acceptance writes a verified docs/shipped/ link when delivered).
Source: <what prompted this — conversation, article, incident, client request>

## Problem

What's wrong or missing, in the originator's own terms. Who feels it, how often, what it costs.

## Proposed outcome

What "reached" looks like — the destination, concrete enough to measure against. Not a design.

## Acceptance

How we'd know this worked — in observable terms, written **now**, before anything is built.

Each line is a check a person can actually perform: what you do, and what should happen. Not tests, not a QA plan — the outcome restated so it can be *checked*, and checked **more than once**: against the local article before shipping, and against production after. The same lines both times.

**Write them for a stranger.** Whoever adjudicates this will not have been in the room — that is the entire point of adjudication, and it is why these are written now rather than at the end. A check that needs you to explain it can only be executed by the one party disqualified from executing it: the person who did the work.

- [ ] A1: <do this> → <this happens>
- [ ] A2: <do this> → <this happens>

Three or four is usually right; a long list means this is really several intents. Where a check can't be automated, say how it's done by hand — a named manual check beats a missing one. Where a check can't be performed at all, say that too; an honest gap here is a decision to make now rather than a surprise at Ship.

**If you can't write a single line here, the Proposed outcome isn't concrete yet.** Go back up and sharpen it — that's the signal this section exists to give.

## Evidence requirements

Optional for legacy intents; **required once the Execution agreement below is approved.** One fenced JSON object mapping acceptance IDs to the evidence channels that must independently confirm them — `automated` (tests, scripts), `ui` (real interactions and captures), `state` (persistence read through a non-UI channel), `human` (a recorded human check). Declare channels for every acceptance criterion. A UI criterion needs `ui`; behavior that reads or changes persisted data also needs `state`. Reserved product or design choices need `human`. `ship-acceptance`'s validator enforces this mapping mechanically: the delivery record must echo it exactly and supply per-channel evidence, or readiness is blocked.

```json
{
  "A1": ["automated"],
  "A2": ["ui", "state"]
}
```

## Affected users and systems

People, repos, services, files, external systems. Anything that changes or must be consulted.

## Constraints

What's fixed: technology, policy, budget, timeline, things that must not change.

## Open questions

The fog — decisions you can see coming but can't phrase sharply yet. Leave them open; the next stage resolves them.

## Size call

One session → build it (plan mode / `/implement`). Multi-session → `/wayfinder`, destination: "<one sentence from Proposed outcome>".

Map Notes for charting (fast grill, seat on): Taste for this effort: <the two or three things the originator wants to decide personally; blank means almost everything technical runs silent>.

## Agreement notes

Optional. This is the **one** place the `dc-autonomy-v1` opt-in lives — no second policy store anywhere. Leave it out entirely for legacy behavior. If present, it is one fenced JSON object; skills and the build-swarm runtime read it from the accepted intent (the runtime is handed it explicitly as `--agreement <repo-relative-intent>`). An unknown, malformed, duplicate, or ambiguous agreement **fails closed** — it never falls back to legacy permission. The heading must be exactly `## Execution agreement` (level 2, exact case, no decoration) and its section must contain only the one fenced JSON block; a near-miss heading — a date suffix, a capital A, a `#`/`###` level — is rejected at both the build runtime and ship validation, never treated as absence. The same heading exactness applies to `## Evidence requirements`. Existing user instructions and host permissions always outrank agreement values.

**`approved` stays `false` in every template and scaffold.** It flips to `true` only to record the originator's actual authorization of this scope — never set by a tool, never defaulted, never inherited from another intent or a global setting. An approved agreement must be accompanied by the Evidence requirements block above.

Field notes: `actions` lists only what applies — the defaults above never imply publishing, client messages, production, spending, or privileged access. `build` limits are ceilings (`max_worker_attempts` ≤ 4, `recovery_cycles` ≤ 1, `max_tasks` ≤ 3); they may be lowered, never raised, and the runtime rejects malformed values. `frontend_checkpoints` reserves the originator's meaningful frontend choices at those named points even inside an approved scope.

## Execution agreement

```json
{
  "policy": "dc-autonomy-v1",
  "approved": false,
  "scope": "<one sentence: exactly the work this agreement covers, across sessions and worker packets>",
  "actions": ["local-edit", "local-test", "local-commit", "ringer-review", "ringer-build"],
  "technical_choices": ["<each reversible technical choice the agent may settle without asking>"],
  "frontend_checkpoints": ["prototype", "final-demo"],
  "test_targets": ["<suite or command the work must keep green>"],
  "review": {
    "seats": ["gpt-6-astra", "claude-fable-5"],
    "max_rounds": 3,
    "independent_confirmation": true
  },
  "build": {
    "max_worker_attempts": 4,
    "recovery_cycles": 1,
    "max_tasks": 3
  }
}
```
