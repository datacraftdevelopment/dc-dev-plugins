# WORKFLOW — how Joe works

**Joe's binding of [SDLC.md](./SDLC.md).** The spec says what the stages are and where a human has to stand. This says how *this stack* executes them. It names tools on purpose and assumes they're installed — Ringer, an authenticated Codex CLI, Matt Pocock's skills, the `_Core/library` skills. **This is not a generic workflow and shouldn't be written as one.** Anyone reading it who doesn't have that stack wants `SDLC.md`, not this file.

The engine is Matt Pocock's skill set. **pm fits around it, never the reverse.** pm is exactly two layers, plus one hook:

1. **The on-ramp** — `discovery`: riff until the shape is visible, write `docs/intent/<slug>.md`, make the size call.
2. **The session layer** — `whats-next` · `stepping-away` (· `checkpoint`): per-session, per-person append-only logs in `_pm/`. Never authoritative. `verify-before-done` gates the completion claims those rituals record. The unit is the **session**, not the day — sessions are kept short, several a day is the normal shape.

Plus the `credential-guard` hook, because [skills advise and hooks enforce](./SDLC.md#the-three-steering-layers). And two utility skills outside the stage chain: `okf` (format contract for the opt-in `knowledge/` bundle) and `granola-transcript` (transcripts into gitignored `_pm/transcripts/`). Anything else in pm justifies itself or gets deleted — the `dashboard` stage board failed that test and was deleted in 0.10.

## The binding

| Stage | Artifact, concretely | Owned by |
|---|---|---|
| **Discover** | `docs/intent/<slug>.md` committed, on its own | `discovery` (pm) |
| **Chart** | wayfinder map open → cleared | `/wayfinder` → `/grilling` + `/domain-modeling`, `/prototype`, `/research` |
| **Spec** | spec on the tracker | `/to-spec` |
| **Ticket** | tickets with blocking edges | `/to-tickets` |
| **Build** | diffs, tests | `/implement` + `/tdd`; plan mode for one-session work |
| **Verify** | fresh test output pasted; triaged findings | `verify-before-done` (pm) · `/code-review` · `cross-review-gate` |
| **Ship** | — **not bound yet, see below** | — |
| **Learn** | incident → a new `docs/intent/` entry | feeds back to Discover |

**Small work** (fits one session) skips Chart → Ticket: Discover → Build → Verify → Ship. **Trivial edits** skip everything. **Bugs** → `/diagnosing-bugs` (failing test first), then Verify.

Decisions go to `docs/adr/` (Matt's home), never `_pm/`. Work items live on the tracker — GitHub Issues in a team, local markdown for solo repos — never in a task file. Projects from pm ≤ 0.7 carrying `TASKS.md` / `_pm/decisions/` / `context-map.md`: see `MIGRATION-0.8.md`.

## The open gap: Ship

`SDLC.md` requires three things at Ship. One is now bound, two aren't.

- ✅ **Acceptance checks written at Discover** — as of 0.13.0 the intent template carries an **Acceptance** section and `discovery` treats it as non-optional. Observable checks, three or four, written before anything is built.
- ❌ **Run against the real thing locally, and again in production.** Nothing runs them. `verify-before-done` is deliberately a *disposition* ("never claim without fresh evidence"), not a prescription of what to run — the right rule at the wrong altitude for "did a human click it and did it work."
- ❌ **A terminating artifact.** The chain still ends at diffs. Proposed: `docs/shipped/<slug>.md` carrying the intent link, the acceptance checks, local and production evidence, review dispositions, and who approved.

What's left is an **adjudicator, not a self-check** (`SDLC.md` § Who adjudicates). It reads the Acceptance block cold, exercises the real thing for *this* stack (browser for a web app, ADT Helper for FileMaker, curl for an API), and returns a verdict per check. It is never asked whether the work is finished — it is handed the criteria and it checks. The working agent doesn't run it on itself; `verify-before-done` is that agent's floor, and a floor isn't a verdict.

Then it stops for the human to deploy — **Claude never touches production** — and re-runs the same checks against prod after.

This is the Ringer principle applied to *done* rather than to *correct*: the worker never self-reports, the criteria are stated up front, and a separate seat executes them. It's the same argument already paying for the fresh-context seat at the review gates below.

Riff: `sdlc/RIFF.md`. **The remaining two stay unbound rather than papered over** — an unowned row is visible; a vague sentence pretending to own it is not.

## Gates

Gates run at stage boundaries, never inside one. Discovery and grilling are gate-free — a gate on a half-formed thought produces noise.

All three gates are `cross-review-gate` (library skill). Only the artifact and the framing sentence change; there is no separate pre-mortem skill because the framing *is* the whole difference and it belongs in the brief.

| Boundary | Default? | Framing in `brief.md` |
|---|---|---|
| **Intent accepted** | optional — the *pre-mortem* slot | "Assume this shipped and the client wasn't happy. Narrate how." Wrong problem, wrong outcome, wrong size. Correctness can't be judged yet; plausibility of failure can. |
| **Plan finalized** | **yes** | Is the plan sound; what's missing; which decision is most likely wrong. |
| **Chunk of code green** | **yes** | Correctness, spec fidelity, standards. |

### The panel

Ringer where installed — Ringside on screen, raw worker logs, run JSON, and an executed check that fails off-brief or evidence-free reviews before they cost a triage pass. The `codex-companion.mjs` path is the fallback, and it's a dark background task: temp-dir state, task output the only record. Save it immediately.

Two seats, two diversity axes:

- **`engine: codex`** — cross-vendor detection. In both 2026-07 proving rounds, codex caught something no Anthropic seat did. It doesn't get dropped.
- **`engine: claude, model: claude-sonnet-5`** — fresh-context detection. Same weights as the orchestrator, zero conversation context: it reads what's on the page, not what I meant. When it flags something I missed, the weights match, so the delta *is* my anchoring — either I hold context that refutes it (cite it under Disagree) or the finding is real. **Escalate to `claude-fable-5` when the boundary touches live data** — migrations, deploys, schema. That operational tail is exactly where Fable was sole finder (4 of 12 findings, 2026-07-27).

**Consensus rule (2026-07-28):** both seats + verified → **Agree, applies under standing consent.** One seat only → **Hold, marked *discuss*** — however well it verified. The sole-finder items *are* the conversation worth having; the proving rounds put every genuinely interesting judgment call in that set.

Two hard edges: consensus never reclassifies the risk tail — a both-seats finding whose fix touches Hold territory still Holds, because it's blast radius not vote count. And a both-seats finding that verification **refutes** is itself a discrepancy: report it, never silent-drop it.

**Freeze the artifact while the panel is in flight.** Applying fixes mid-run contaminates any seat that finishes late (learned 2026-07-27: a retry landed mid-apply and its findings had to be discarded as incomparable).

**Offer at the boundary, dispatch on the yes — never auto-fire.** A dispatch spends real quota and takes minutes.

## `docs/` is shared record, `_pm/` is personal log

| | `docs/` | `_pm/` |
|---|---|---|
| Holds | intent, ADRs, `CONTEXT.md`, agent config (`docs/agents/`) | Intent-of-the-session, session entries, what I'm picking up |
| Authoritative? | **Yes** — with the tracker | **No** — if it disagrees with the tracker, the tracker wins |
| Shared? | Yes — collaborators and clients read it | Per-session, per-person (`_pm/sessions/YYYY-MM-DD-<name>[-N].md`), append-only |
| Written by | `discovery`, `/domain-modeling`, `/grilling`, `setup-matt-pocock-skills` | `whats-next`, `checkpoint`, `stepping-away` |

`_pm/` records *what I did and what I'm doing* — never *what is true*.

## Session shape

- **Open** — `whats-next`: tracker frontier + the last session or two, propose a pick-up, draft this session's Intent block.
- **Anything non-trivial** — `discovery`, then the size call picks the road: one session → plan mode or `/implement`; multi-session or foggy → `/wayfinder` with the intent attached.
- **Mid-session** — normally close and reopen; a fresh Intent is the cleanest re-aim and keeps the thread short. `checkpoint` only when the session can't be broken. `/handoff` when a session outgrows itself.
- **Any completion claim** — `verify-before-done`: run it fresh, read it, paste it.
- **Stage boundary** — the gate schedule above.
- **Close** — `stepping-away`: Intent vs shipped, session entry, durable knowledge routed to the library. Then open the next one.

## Team model

Work → pm records the session → push the branch → the next person pulls and merges. Works because `_pm/` files are per-person and append-only (no conflicts) and nothing in `_pm/` is a state store. Trackers and `docs/` carry shared truth across people and machines.

## Source

Workflow of record for DataCraft repos; the global `Agentic/CLAUDE.md` routing section points here. Doctrine: [SDLC.md](./SDLC.md). Shape history: `docs/intent/pm-workflow-reshape.md`, `docs/intent/pm-010-lightening.md`, and the layer split in `sdlc/RIFF.md` (2026-09-03).
