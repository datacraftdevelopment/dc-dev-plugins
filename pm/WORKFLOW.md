# WORKFLOW — how Joe works

**Joe's binding of [SDLC.md](./SDLC.md).** The spec says what the stages are and where a human has to stand. This says how *this stack* executes them. It names tools on purpose and assumes they're installed — Ringer, an authenticated Codex CLI, Matt Pocock's skills, the `_Core/library` skills. **This is not a generic workflow and shouldn't be written as one.** Anyone reading it who doesn't have that stack wants `SDLC.md`, not this file.

The engine is Matt Pocock's skill set. **pm fits around it, never the reverse.** pm is exactly two layers, plus one pace rule, plus one hook:

1. **The on-ramp** — `discovery`: riff until the shape is visible, write `docs/intent/<slug>.md`, make the size call.
2. **The session layer** — `whats-next` · `stepping-away` (· `checkpoint`): per-session, per-person append-only logs in `_pm/`. Never authoritative. `verify-before-done` gates the completion claims those rituals record. The unit is the **session**, not the day — sessions are kept short, several a day is the normal shape.
3. **The pace rule** — `fast-grill` (0.14): technical questions in a grilling round go to a second-vendor seat with their recommended answers and come back as rulings; the human answers only taste, one-way doors, and splits. It is what makes the heavy stack affordable to run on every project.

Plus the `credential-guard` hook, because [skills advise and hooks enforce](./SDLC.md#the-three-steering-layers). And two utility skills outside the stage chain: `okf` (format contract for the opt-in `knowledge/` bundle) and `granola-transcript` (transcripts into gitignored `_pm/transcripts/`). Anything else in pm justifies itself or gets deleted — the `dashboard` stage board failed that test and was deleted in 0.10.

## The binding

| Stage | Artifact, concretely | Owned by |
|---|---|---|
| **Discover** | `docs/intent/<slug>.md` committed, on its own | `discovery` (pm) |
| **Chart** | wayfinder map open → cleared | `/wayfinder` → `/grilling` + `/domain-modeling`, `/prototype`, `/research` — every grilling round under `fast-grill` (pm) |
| **Spec** | spec on the tracker | `/to-spec` |
| **Ticket** | tickets with blocking edges | `/to-tickets` — the approval step under `fast-grill` |
| **Build** | diffs, tests | one ticket or one-session work: `/implement` + `/tdd`, or plan mode · **a ticket frontier with committed checks: `build-swarm`'s loop at `--wave 1`, the default (0.15.1)** — `scripts/loop.py` works the frontier to empty unattended through Ringer, one ticket at a time, one commit per ticket, parking what fails; `--wave 2+` is the operator's call per frontier after the parallel-safety screen |
| **Verify** | fresh test output pasted; triaged findings | `verify-before-done` (pm) · `/code-review` · `cross-review-gate` |
| **Ship** | `docs/shipped/<slug>.md` with accepted intent snapshot, candidate/delivered revisions, independent evidence and dispositions | `ship-acceptance` (pm); human applies production |
| **Learn** | incident → a new `docs/intent/` entry; durable craft → the library, under the bar in `stepping-away` | feeds back to Discover |

**Small work** (fits one session) skips Chart → Ticket: Discover → Build → Verify → Ship. **Trivial edits** skip everything. **Bugs** → `/diagnosing-bugs` (failing test first), then Verify.

Decisions go to `docs/adr/` (Matt's home), never `_pm/`. Work items live on the tracker — GitHub Issues in a team, local markdown for solo repos — never in a task file. Projects from pm ≤ 0.7 carrying `TASKS.md` / `_pm/decisions/` / `context-map.md`: see `MIGRATION-0.8.md`.

## Fast grill — the pace rule

`/grilling` prints a recommended answer under every question, and on technical questions Joe is deferring to the model anyway. So the technical bucket of each round is not shown to him: it goes, with the recommendations, to one Ringer task on the **Astra seat** (`engine: codex, model: gpt-6-astra` — kit `Agent/Ringer/local/templates/grill-review/`), and comes back as `agree` (→ a ruling), `disagree` (→ a seat-split question for Joe, both positions shown), `taste` (→ a question for Joe), or `door` (→ a one-way-door question for Joe; the seat's check on the bucket the recommending model must never judge alone). One-way doors and user challenges never go to the seat and are never auto-taken, whatever else they are; taste is asked; only then does the technical tie-break apply. Every ruling is one ledger line — decided · why · cost if wrong · who agreed — in the ticket's resolution comment, the map body, or the plan, and reversing one is a reply naming it.

**`fast-grill` (pm) is canonical for the buckets, the seat, the round, and the ledger.** What this file owns is the schedule: fast grill is the **default** for every grilling round at Chart (both charting grills, the destination question itself excepted), inside every grilling ticket, at `/to-tickets`' approval step (granularity to the seat; blocking edges shown, never auto-taken; publish on Joe's nod), and on a plan being grilled in plan mode (which runs `(unseated)` by construction, since plan mode can't dispatch Ringer; the skill says how to seat it after approval). It is off for discovery (no frontier to sort) and prototype tickets (the reaction is the ticket). A map carries the switch in its `## Notes` (`Seat: on | off`, plus *Taste for this effort*); `discovery` hands that line over with the intent. Seat availability and degraded behavior are owned by the host-adapted `fast-grill` skill; follow that procedure.

This is not a gate. The seat here judges a recommendation before it becomes a ruling; the gates below judge an artifact at a stage boundary. Both are the same principle — a model never approves its own answer — at different altitudes.

## Build-swarm — Build when tickets exist, and its loop at `--wave 1` is the default

`/to-tickets` emits a DAG: tracer-bullet slices with acceptance criteria and blocking edges. Before unattended dispatch, run build-swarm's preparation procedure to normalize blockers, author committed checks and record ownership. Automatic preparation/loop execution currently uses local markdown tickets; GitHub retains the manual build procedure. A loop `--dry-run` may park and commit tickets, so it is not a read-only preview. When the prepared frontier holds tickets that carry committed checks, `build-swarm` (library, next to `ringer` and `cross-review-gate`, because it dispatches through Ringer) turns each layer into one Ringer worktrees wave: one task per ticket, the ticket and the map's settled rulings inlined as the spec, its runnable acceptance criteria plus the owned area's tests as the executed check (never the full suite, which touches the singletons workers would fight over), patches exported outside the worktree. The orchestrator applies patches in dependency order, runs the full suite on the integrated tree, commits one ticket per commit, closes each ticket with its evidence, and takes the next layer. Chunk green → the gate below, unchanged.

**The loop at `--wave 1` is how Build runs by default (0.15.1, the verdict of twelve two-seat gate rounds on 2026-09-06/07).** `build-swarm`'s `scripts/loop.py` does the above unattended: the script owns selection and stopping, Ringer owns execution and the verdict, the worker owns implementation; a wave never starts on a dirty tree, a red suite, or a moved `HEAD`; every ticket is proved red before dispatch; the loop's own commits bypass the target repo's hooks and signing and are checked against what was tested; what fails parks `needs-human` and the run continues; a ticket a human wrote badly is reported by name, never guessed at. Invocation and the ticket lines it reads are in the skill. **Wider waves (`--wave 2+`) are the operator's call, per frontier, after the skill's parallel-safety screen** — both seats held that line in every round: the pilot proved a parallel wave works, not that an arbitrary frontier is safe to run in parallel. `/implement` + `/tdd` stays the road for a single ticket or work that fits one session. Running a wave by hand (filling the kit yourself) is still legitimate; it is the same loop with a human doing the selection.

What "went well" meant, so the default is a decision with evidence behind it. The gate: twelve rounds, Astra (codex) and Fable (claude) each round, 108 findings, every one applied and pinned by a test (96 tests), until round 12 when both seats reported no remaining P1/P2 in the same round and gave the same verdict: default at `--wave 1`, wider waves an operator option. The proving runs on the scratch pilot, one after each round's fixes: twenty tickets built by the loop, every worker attempt first-try, including a dependent pair across two waves in one run, a two-ticket parallel wave, four tickets built through a re-staging pre-commit hook and a commit-msg linter planted in the repo, a CRLF ticket; and three tickets the loop correctly refused to build (an unsatisfiable check parked after two attempts, a duplicated Status line and a latin-1 byte both reported as malformed by name with the run continuing). A real fast-grill seat round preceded the second layer (five questions, three agreed with file references, two handed back as taste). What the pilot could not show, and the seats said so: a dependency-managed repo (the red proof runs in a bare worktree), a hand-maintained tracker at scale, a real frontier screened for parallel safety. Those are the first-real-repo watch items. Records: `.review-gate/2026-09-06-loop-chain/triage.md` (every finding and its disposition), dc-loop `docs/intent/loop-experiment.md` and `_pm/sessions/2026-09-06-joe-2.md`, `-3.md`.

What this file owns: the trigger (a ticket frontier with committed checks; one ticket goes to `/implement`) and four preconditions. A **committed baseline** — worktrees are cut from `HEAD`. A **workdir outside the repo and outside Dropbox** — Ringer creates every worktree inside the workdir, so that path decides whether worktree contents sync to the cloud (the repo's `.git/worktrees` admin entries still do; the skill prunes them before each wave). At least one **acceptance criterion a script can run** per ticket, and it must be **red at `HEAD`** before dispatch — the skill proves that itself, because the kit's check can't; criteria nothing can run are listed on the ticket as *Unproven by check* and carried into the gate brief. **Not a wide-refactor group** — `/to-tickets`' expand → migrate batches → contract sequence promises green only at its integrate ticket and goes to `/implement`. The loop, the parallel safety check, and the manifest kit are the skill's. Designed and gated 2026-09-06 (record in `.review-gate/2026-09-06-pm-014-fast-grill-build-swarm/`), proven the same evening on the pilot as described above.

## Ship — acceptance against the delivered thing

`ship-acceptance` owns the handoff from verified implementation to delivery. It reads the accepted intent cold, sends its criteria to an evaluator who did not implement the candidate, and records local/staging and delivered results against exact revisions in `docs/shipped/<slug>.md` with a JSON companion and the accepted intent snapshot. Its record validator checks completeness and identity consistency; the evaluator supplies the actual evidence.

Status is **blocked**, **ready-for-release**, **shipped**, or **released-with-exceptions**. An implementation ticket may close on its contract without marking the parent intent shipped. Missing checks remain visible; an explicit human exception does not become an unqualified pass. For documents and tools, the delivered artifact and use context replace a production endpoint.

The human applies production. After confirmed delivery, the same checks run against the actual delivered revision. Live-data writes require an explicitly approved safe procedure. Completion is linked back to the intent so `whats-next` can exclude a delivered stream only after reading its evidence. This binds the procedure; a successful rehearsal does not certify untested browser, FileMaker, or API stacks.

## Gates

Gates run at stage boundaries, never inside one. Discovery and grilling are gate-free — a gate on a half-formed thought produces noise. (The fast-grill seat inside a grilling round is not a gate; see above.)

All three gates are `cross-review-gate` (library skill). Only the artifact and the framing sentence change; there is no separate pre-mortem skill because the framing *is* the whole difference and it belongs in the brief.

| Boundary | Default? | Framing in `brief.md` |
|---|---|---|
| **Intent accepted** | optional — the *pre-mortem* slot | "Assume this shipped and the client wasn't happy. Narrate how." Wrong problem, wrong outcome, wrong size. Correctness can't be judged yet; plausibility of failure can. |
| **Plan finalized** | **yes** | Is the plan sound; what's missing; which decision is most likely wrong. |
| **Chunk of code green** | **yes** | Correctness, spec fidelity, standards. |

### The panel

Owned by `cross-review-gate`, and it stays in `_Core/library/skills/agent-operations/` next to `ringer` — it dispatches through Ringer, so it lives with its transport. **That skill is canonical for how a gate runs**: the two seats and why each earns its place, the Fable escalation for live-data boundaries, the consensus rule and its two hard edges, the triage buckets, freeze-while-in-flight, and offer-at-boundary / dispatch-on-yes. Don't restate any of it here — one statement, or it forks.

What this file owns is the schedule above: *when* a gate fires in the stage chain, and the framing sentence that goes in its `brief.md`.

Why the panel is shaped the way it is — a reader with no conversation context, judging what's on the page rather than what you meant — is [`SDLC.md` § Who adjudicates](./SDLC.md#who-adjudicates). Same principle the Ship adjudicator will run on.

## `docs/` is shared record, `_pm/` is personal log

| | `docs/` | `_pm/` |
|---|---|---|
| Holds | intent, ADRs, `CONTEXT.md`, agent config (`docs/agents/`) | Intent-of-the-session, session entries, what I'm picking up |
| Authoritative? | **Yes** — with the tracker | **No** — if it disagrees with the tracker, the tracker wins |
| Shared? | Yes — collaborators and clients read it | Per-session, per-person (`_pm/sessions/YYYY-MM-DD-<name>[-N].md`), append-only |
| Written by | `discovery`, `/domain-modeling`, `/grilling`, `setup-matt-pocock-skills` | `whats-next`, `checkpoint`, `stepping-away` |

`_pm/` records *what I did and what I'm doing* — never *what is true*. Rulings from `fast-grill` are decisions, so they live with the tracker (ticket comments, the map body), never in `_pm/`.

## Session shape

- **Open** — `whats-next`: tracker frontier + the last session or two, propose a pick-up, draft this session's Intent block.
- **Anything non-trivial** — `discovery`, then the size call picks the road: one session → plan mode or `/implement`; multi-session or foggy → `/wayfinder` with the intent attached and the fast-grill Notes line for the map.
- **Any grilling round** — `fast-grill`: technical bucket to the seat, the rest to the human, rulings ledgered.
- **Before another ticket or manually controlled wave** — reread this conversation's bound session Intent/latest re-aim and reconcile with shared docs and the tracker. A running unattended loop does not read personal notes as control signals.
- **A ticket frontier with committed checks** — `build-swarm`'s loop at `--wave 1`, from a committed baseline and a green suite, workdir outside Dropbox; come back to a report, closed tickets, and a `needs-human` queue. `--wave 2+` only after the parallel-safety screen, per frontier. One ticket → `/implement` + `/tdd`.
- **Mid-session** — normally close and reopen; a fresh Intent is the cleanest re-aim and keeps the thread short. `checkpoint` only when the session can't be broken. `/handoff` when a session outgrows itself.
- **Any completion claim** — `verify-before-done`: run it fresh, read it, paste it.
- **Stage boundary** — the gate schedule above.
- **Close** — `stepping-away`: Intent vs shipped, session entry, durable knowledge routed to the library under the bar (would the next engineer, without this note, repeat the mistake?). Then open the next one.

## Team model

Work → pm records the session → push the branch → the next person pulls and merges. Works because `_pm/` files are per-person and append-only (no conflicts) and nothing in `_pm/` is a state store. Trackers and `docs/` carry shared truth across people and machines.

## Source

Workflow of record for DataCraft repos; the global `Agentic/CLAUDE.md` routing section points here. Doctrine: [SDLC.md](./SDLC.md). Shape history: `docs/intent/pm-workflow-reshape.md`, `docs/intent/pm-010-lightening.md`, the layer split in `sdlc/RIFF.md` (2026-09-03), and the 0.14 plan (fast grill, the Astra seat, build-swarm) in this repo's `_pm/2026-09-06-build-swarm-and-fast-grill.html`, which was chosen after reading the candidate plugins from source.
