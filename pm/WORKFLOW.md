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
| **Build** | diffs, tests | one ticket or one-session work: `/implement` + `/tdd`, or plan mode · **a ticket frontier with committed checks: `build-swarm`'s loop, the default (0.15)** — `scripts/loop.py` works the frontier to empty unattended through Ringer, one commit per ticket, parking what fails |
| **Verify** | fresh test output pasted; triaged findings | `verify-before-done` (pm) · `/code-review` · `cross-review-gate` |
| **Ship** | — **not bound yet, see below** | — |
| **Learn** | incident → a new `docs/intent/` entry; durable craft → the library, under the bar in `stepping-away` | feeds back to Discover |

**Small work** (fits one session) skips Chart → Ticket: Discover → Build → Verify → Ship. **Trivial edits** skip everything. **Bugs** → `/diagnosing-bugs` (failing test first), then Verify.

Decisions go to `docs/adr/` (Matt's home), never `_pm/`. Work items live on the tracker — GitHub Issues in a team, local markdown for solo repos — never in a task file. Projects from pm ≤ 0.7 carrying `TASKS.md` / `_pm/decisions/` / `context-map.md`: see `MIGRATION-0.8.md`.

## Fast grill — the pace rule

`/grilling` prints a recommended answer under every question, and on technical questions Joe is deferring to the model anyway. So the technical bucket of each round is not shown to him: it goes, with the recommendations, to one Ringer task on the **Astra seat** (`engine: codex, model: gpt-6-astra` — kit `Agent/Ringer/local/templates/grill-review/`), and comes back as `agree` (→ a ruling), `disagree` (→ a seat-split question for Joe, both positions shown), `taste` (→ a question for Joe), or `door` (→ a one-way-door question for Joe; the seat's check on the bucket the recommending model must never judge alone). One-way doors and user challenges never go to the seat and are never auto-taken, whatever else they are; taste is asked; only then does the technical tie-break apply. Every ruling is one ledger line — decided · why · cost if wrong · who agreed — in the ticket's resolution comment, the map body, or the plan, and reversing one is a reply naming it.

**`fast-grill` (pm) is canonical for the buckets, the seat, the round, and the ledger.** What this file owns is the schedule: fast grill is the **default** for every grilling round at Chart (both charting grills, the destination question itself excepted), inside every grilling ticket, at `/to-tickets`' approval step (granularity to the seat; blocking edges shown, never auto-taken; publish on Joe's nod), and on a plan being grilled in plan mode (which runs `(unseated)` by construction, since plan mode can't dispatch Ringer; the skill says how to seat it after approval). It is off for discovery (no frontier to sort) and prototype tickets (the reaction is the ticket). A map carries the switch in its `## Notes` (`Seat: on | off`, plus *Taste for this effort*); `discovery` hands that line over with the intent. No seat available → rulings are taken directly and marked `(unseated)`, said out loud.

This is not a gate. The seat here judges a recommendation before it becomes a ruling; the gates below judge an artifact at a stage boundary. Both are the same principle — a model never approves its own answer — at different altitudes.

## Build-swarm — Build when tickets exist, and its loop is the default

`/to-tickets` emits a DAG: tracer-bullet slices with acceptance criteria and blocking edges. When the frontier holds tickets that carry committed checks, `build-swarm` (library, next to `ringer` and `cross-review-gate`, because it dispatches through Ringer) turns each layer into one Ringer worktrees wave: one task per ticket, the ticket and the map's settled rulings inlined as the spec, its runnable acceptance criteria plus the owned area's tests as the executed check (never the full suite, which touches the singletons workers would fight over), patches exported outside the worktree. The orchestrator applies patches in dependency order, runs the full suite on the integrated tree, commits one ticket per commit, closes each ticket with its evidence, and takes the next layer. Chunk green → the gate below, unchanged.

**The loop is how Build runs by default (0.15, Joe's call after the 2026-09-06 chain run).** `build-swarm`'s `scripts/loop.py` does the above unattended: the script owns selection and stopping, Ringer owns execution and the verdict, the worker owns implementation; a wave never starts on a dirty tree or a red suite; every ticket is proved red before dispatch; what fails parks `needs-human` and the run continues. Invocation and the ticket lines it reads are in the skill. Two escape hatches, both deliberate: `--wave 1` for a repo where parallelism hasn't been earned yet, and `/implement` + `/tdd` for a single ticket or work that fits one session. Running a wave by hand (filling the kit yourself) is still legitimate; it is the same loop with a human doing the selection.

What "went well" meant, so the default is a decision with evidence behind it: on the scratch pilot, seven tickets were built by the loop across four runs (Astra on codex, ~270k tokens); three sequentially with the suite green at every commit, then three in one parallel wave, all first-try after the kit's summary rule moved into the hard rules; an unsatisfiable ticket parked after two attempts with the run continuing past it, and the worker's own summary refused to fake it; a real fast-grill seat round preceded the second layer (five questions, three agreed with file references, two handed back as taste). The finished CLI works end to end. Records: dc-loop `docs/intent/loop-experiment.md`, `_pm/sessions/2026-09-06-joe-2.md`, and the gate in `.review-gate/2026-09-06-loop-chain/`.

What this file owns: the trigger (a ticket frontier with committed checks; one ticket goes to `/implement`) and four preconditions. A **committed baseline** — worktrees are cut from `HEAD`. A **workdir outside the repo and outside Dropbox** — Ringer creates every worktree inside the workdir, so that path decides whether worktree contents sync to the cloud (the repo's `.git/worktrees` admin entries still do; the skill prunes them before each wave). At least one **acceptance criterion a script can run** per ticket, and it must be **red at `HEAD`** before dispatch — the skill proves that itself, because the kit's check can't; criteria nothing can run are listed on the ticket as *Unproven by check* and carried into the gate brief. **Not a wide-refactor group** — `/to-tickets`' expand → migrate batches → contract sequence promises green only at its integrate ticket and goes to `/implement`. The loop, the parallel safety check, and the manifest kit are the skill's. Designed and gated 2026-09-06 (record in `.review-gate/2026-09-06-pm-014-fast-grill-build-swarm/`), proven the same evening on the pilot as described above.

## The open gap: Ship

`SDLC.md` requires three things at Ship. One is now bound, two aren't.

- ✅ **Acceptance checks written at Discover** — as of 0.13.0 the intent template carries an **Acceptance** section and `discovery` treats it as non-optional. Observable checks, three or four, written before anything is built.
- ❌ **Run against the real thing locally, and again in production.** Nothing runs them. `verify-before-done` is deliberately a *disposition* ("never claim without fresh evidence"), not a prescription of what to run — the right rule at the wrong altitude for "did a human click it and did it work."
- ❌ **A terminating artifact.** The chain still ends at diffs. Proposed: `docs/shipped/<slug>.md` carrying the intent link, the acceptance checks, local and production evidence, review dispositions, and who approved.

What's left is an **adjudicator, not a self-check** (`SDLC.md` § Who adjudicates). It reads the Acceptance block cold, exercises the real thing for *this* stack (browser for a web app, ADT Helper for FileMaker, curl for an API), and returns a verdict per check. It is never asked whether the work is finished — it is handed the criteria and it checks. The working agent doesn't run it on itself; `verify-before-done` is that agent's floor, and a floor isn't a verdict.

Then it stops for the human to deploy — **Claude never touches production** — and re-runs the same checks against prod after.

This is the Ringer principle applied to *done* rather than to *correct*: the worker never self-reports, the criteria are stated up front, and a separate seat executes them. It's the same argument already paying for the fresh-context seat at the review gates below.

Riff: `sdlc/RIFF.md`. **The remaining two stay unbound rather than papered over** — an unowned row is visible; a vague sentence pretending to own it is not.

A candidate binding already researched and live-verified, from the parked dc-loop tool (`_Tools/dc-loop/.scratch/dc-loop-plugin/research/server-side-gate-pattern.md`, 2026-08-28): CI runs on the pushed SHA; a ruleset lets `main` move only on green plus a PR (GitHub Pro on private personal repos; a `needs:`-chained CI→deploy workflow is the Free-plan degrade); deploy is a `main`-push workflow in a serialized concurrency group, keyed by SHA and idempotent; the human's gate is the merge. That answers "run against the real thing" for a web repo with CI and makes the PR the terminating artifact. It is not bound because no repo has run it yet — the same proving rule as everything else in 0.14.

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
- **A ticket frontier with committed checks** — `build-swarm`'s loop, from a committed baseline and a green suite, workdir outside Dropbox; come back to a report, closed tickets, and a `needs-human` queue. One ticket → `/implement` + `/tdd`.
- **Mid-session** — normally close and reopen; a fresh Intent is the cleanest re-aim and keeps the thread short. `checkpoint` only when the session can't be broken. `/handoff` when a session outgrows itself.
- **Any completion claim** — `verify-before-done`: run it fresh, read it, paste it.
- **Stage boundary** — the gate schedule above.
- **Close** — `stepping-away`: Intent vs shipped, session entry, durable knowledge routed to the library under the bar (would the next engineer, without this note, repeat the mistake?). Then open the next one.

## Team model

Work → pm records the session → push the branch → the next person pulls and merges. Works because `_pm/` files are per-person and append-only (no conflicts) and nothing in `_pm/` is a state store. Trackers and `docs/` carry shared truth across people and machines.

## Source

Workflow of record for DataCraft repos; the global `Agentic/CLAUDE.md` routing section points here. Doctrine: [SDLC.md](./SDLC.md). Shape history: `docs/intent/pm-workflow-reshape.md`, `docs/intent/pm-010-lightening.md`, the layer split in `sdlc/RIFF.md` (2026-09-03), and the 0.14 plan (fast grill, the Astra seat, build-swarm) in this repo's `_pm/2026-09-06-build-swarm-and-fast-grill.html`, which was chosen after reading the candidate plugins from source.
