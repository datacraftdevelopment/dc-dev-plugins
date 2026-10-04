# tc-overlay — files only the TC edition gets

`make-tc-plugins.sh` cuts `tc-plugins` from the public tree and then lays this
folder over it, together with the whole `sdlc/` plugin and pm's private
`session.py`. RCC's public edition gets none of it (decided 2026-10-04).

TC runs Claude Code only: no Ringer, no second vendor. So where the private pm
sends a review to another vendor's seat, this overlay uses a fresh Claude
subagent.

| File | What it is |
|---|---|
| `pm/WORKFLOW.md` | TC's binding of `SDLC.md`: the default loop, sibling sessions, when to review. No orchestrator. |
| `pm/agents/adversary-reviewer.md` | Read-only subagent that tries to break a change against its acceptance lines. |
| `pm/skills/adversary-review/` | When to run that reviewer, what to hand it, what to do with findings. |
| `pm/skills/ship-acceptance/` | Hand-cut from the private skill: Markdown record only, no JSON validator and no Execution agreement. |

Not ported, on purpose: `orchestrate` (2.6x usage as a default), `fast-grill`
(its point is a second vendor), `session-succession` (beta, host-specific),
`board` (reads `.scratch/` tickets; TC's tracker is `docs/TASKS.md`).

Removed for TC by the build script: pm's `granola-transcript` skill and every
mention of it. TC does not use Granola.

Edit here, commit, then re-run the chain. The script aborts if any text it
patches has drifted, and fails the build on any Ringer or private-path word in
the TC tree.
