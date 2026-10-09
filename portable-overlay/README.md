# portable-overlay — what the shared editions' pm has that the private pm does not

The source for the Claude-only pieces of the RCC and TC editions. The shared
editions run on Claude Code alone: no Ringer, no second vendor. So where the
private pm sends a review to another vendor's seat, these use a fresh Claude
subagent.

| File | What it is |
|---|---|
| `pm/WORKFLOW.md` | The shared binding of `SDLC.md`: the default loop, sibling sessions, when to review. No orchestrator. |
| `pm/agents/adversary-reviewer.md` | Read-only subagent that tries to break a change against its acceptance lines. |
| `pm/skills/adversary-review/` | When to run that reviewer, what to hand it, what to do with findings. |
| `pm/skills/ship-acceptance/` | Hand-cut from the private skill: Markdown record only, no JSON validator and no Execution agreement. |

## How it reaches the editions

```
portable-overlay/ + pm/ (gate kit, guard) + pm/scripts/session.py  (here, private)
        │  hand pass, like the rest of the RCC pm cut
        ▼
rcc-plugins/pm                          (RCC credit, public once pushed)
        │  make-dc-plugins.sh
        ▼
dc-plugins                               (local only)
        │  make-tc-plugins.sh
        ▼
tc-plugins                               (plain copy, Joe's credit)
```

From 2026-10-04 RCC and TC carry the same pm. From pm 0.25.0 that pm also carries
what sdlc and ui-test used to be (they were folded into pm, so there is no separate
`sdlc` to pass). The hand pass into
`rcc-plugins`:

- copy the files in this folder over `rcc-plugins/pm/`, and the private
  `pm/scripts/session.py`; set the pm version to the private one. The
  credential guard, the gate kit and the review policy (`hooks/`, `kit/`,
  `agents/`, `templates/`, `GATES.md`, the `credential-guard`, `gate-hooks` and
  `review-policy` skills, the credential and `install_gates` scripts) now live
  in `pm/` itself, so the next pass copies them with the rest of pm and deletes
  `rcc-plugins/sdlc/`. In `GATES.md` the three sentences that name Ringer or
  Codex are rewritten, and the install lines name `FMTrainingTV-AI/rcc-fm`;
- `ui-test` stays out of the shared editions: it needs Ringer and Codex, so the
  pass leaves `skills/ui-test/`, `requirements.txt` and `UI-TEST.md` behind;
- no `granola-transcript` skill and no mention of it.

`make-tc-plugins.sh` fails the build on any Ringer, private-path or Granola
word, so a slip in the hand pass is caught at the TC cut.

Not ported, on purpose: `orchestrate` (2.6x usage as a default), `fast-grill`
(its point is a second vendor), `session-succession` (beta, host-specific),
`board` (reads `.scratch/` tickets; the shared tracker is `docs/TASKS.md`).
