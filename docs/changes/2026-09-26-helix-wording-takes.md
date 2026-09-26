# Helix wording takes (ui-test 0.3.1, pm 0.22.2, fm-dc 0.8.2)

Three sentences taken from Shopify's Helix checkpoint-gate loop, each placed in
a skill that already fires. No new skill, hook, script or tool. Joe accepted all
three on 2026-09-26 from the review artifact; the read that produced them is
`_library/wiki/craft/agents/checkpoint-gate-loop.md`.

**ui-test.** Step 1: when a case compares the app against a reference, the
precondition names the state both must be in and the runner captures both in
that state. Outcomes: a state mismatch between the two captures is `BLOCKED` at
stage `comparison`, which means recapture, not a product FAIL. Step 5: a visual
comparison is scoped to what the change built. The artifact proposed a fourth
verdict, `INVALID`; that would have meant editing both check scripts and their
tests, one rung up from wording, so the existing BLOCKED stage carries it.
`receipt-schema.md` gains the `comparison` stage and a `STATE_MISMATCH` code.

**pm, `orchestrate` §2.** One sentence after the graph table: order nodes by
risk, not size. Skeleton first, one deliberately small slice second, wider nodes
only after those two pass their checks.

**fm-dc, README deploy lane.** For a rebuild or port the existing file is the
spec; derive checkpoint test cases from its DDR, XML and observed behaviour, and
write prose only for what changes. The reference wins when a running reference
exists; the spec wins when the work is new.

**Declined.** The Stop hook (exit 2 until gates pass) from the AI LABS
reconstruction. PM's enforcement layer is `acceptance.py`, which fails closed on
evidence structure; a hook can only tell the agent to keep going.

## How we'll know it helped

- ui-test: the next reference comparison (prototype vs app) either produces a
  `comparison` BLOCKED that saved a wrong verdict, or never needs the row. Count
  both.
- orchestrate: the next orchestrated run's first wave. Did the skeleton node
  catch a shape decision before wider nodes were spent on it? Compare against
  the Marvel run (`docs/research/orchestrate-ringer-field-report-marvel-2026-09-20`).
- fm-dc: the next rebuild engagement. Was a prose spec written for unchanged
  behaviour anyway? If so the note isn't being read.

Outcome: **pending**. Record it in `docs/changes/README.md` when one of these
runs happens.
