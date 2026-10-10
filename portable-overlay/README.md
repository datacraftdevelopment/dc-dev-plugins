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
what sdlc and ui-test used to be, and the editions follow: one pm in every
edition, no separate `sdlc` plugin and no split rule (decided 2026-10-09, GitHub
#6, `factory/decisions.md`). The edition scripts hold no `sdlc` path or version
entries. The hand pass into `rcc-plugins`:

- copy the files in this folder over `rcc-plugins/pm/`, and the private
  `pm/scripts/session.py`; set the pm version to the private one. The
  credential guard, the gate kit and the review policy (`hooks/`, `kit/`,
  `agents/`, `templates/`, `GATES.md`, the `credential-guard`, `gate-hooks` and
  `review-policy` skills, the credential and `install_gates` scripts) live in
  `pm/` itself, so the pass copies them with the rest of pm. The guard arrives
  with pm: there is no `sdlc/` copy to take it from, and the old
  `rcc-plugins/sdlc/` folder is deleted;
- rewrite the sdlc-origin sentences that name Ringer or private paths, or the
  TC cut fails: `GATES.md` (the Ringer/Codex lines near the top, the library
  page path, the two `dc-dev-plugins` install lines, which become
  `FMTrainingTV-AI/rcc-fm`, and the Ringer-workers line near the end),
  `skills/review-policy/SKILL.md` (the `cross-review-gate` sentence) and
  `skills/credential-guard/SKILL.md` (the build-swarm policy-snapshot lines);
- `ui-test` stays out of the shared editions: it needs Ringer and Codex, so the
  pass leaves `skills/ui-test/`, `requirements.txt` and `UI-TEST.md` behind;
- no `granola-transcript` skill and no mention of it.

`make-tc-plugins.sh` fails the build on any Ringer, private-path or Granola
word, so a slip in the hand pass is caught at the TC cut.

Order and reinstall. Run the hand pass and the cuts only after the pm that folds
sdlc in (#5, pm 0.25.0) is on `main`; before that the paths above don't exist.
Students reinstall pm once, and anyone who has the old `sdlc` plugin removes it
(`/plugin uninstall sdlc`) or they carry two copies of the credential guard.
Joe runs the cuts and any push to the public RCC repo himself; agents don't.

Not ported, on purpose: `orchestrate` (2.6x usage as a default), `fast-grill`
(its point is a second vendor), `session-succession` (beta, host-specific),
`board` (reads `.scratch/` tickets; the shared tracker is `docs/TASKS.md`).
