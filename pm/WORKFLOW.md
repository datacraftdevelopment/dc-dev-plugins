# WORKFLOW — how pm fits around the Matt-primary stack

The engine is Matt Pocock's skill set (`/wayfinder`, `/grilling`, `/domain-modeling`, `/prototype`, `/research`, `/to-spec`, `/to-tickets`, `/implement`, `/tdd`, `/code-review`, `/handoff`). **pm fits around its structure, never the reverse.** pm is exactly two layers:

1. **The on-ramp** — `discovery`: riff until the shape is visible, write `docs/intent/<slug>.md`, make the size call.
2. **The session layer** — `whats-next` · `checkpoint` · `stepping-away`: per-person, append-only logs in `_pm/`. Never authoritative. `verify-before-done` gates the completion claims those rituals record.

Plus one deterministic guardrail — the `credential-guard` hook (blocks committing credential-shaped files), because skills advise and hooks enforce. And two **utility skills outside the stage chain**, kept because the projects this plugin stamps need them at hand: `okf` (the format contract for the opt-in `knowledge/` bundle the rituals are aware of) and `granola-transcript` (meeting transcripts land safely in `_pm/transcripts/`, gitignored). Anything else in pm has to justify itself or get deleted — the `dashboard` stage board failed that test and was deleted in 0.10.

## Stages

A stage is defined by **which artifact exists** — never by a status someone updates.

| Stage | Artifact that marks it | Owned by |
|---|---|---|
| **Discover** | `docs/intent/<slug>.md` committed | `discovery` (pm) |
| **Chart** | wayfinder map open → cleared | `/wayfinder` → `/grilling` + `/domain-modeling`, `/prototype`, `/research` |
| **Spec** | spec on the tracker | `/to-spec` |
| **Ticket** | implementation tickets with blocking edges | `/to-tickets` |
| **Build** | diffs, tests | `/implement` + `/tdd`; plan mode for one-session work |
| **Verify** | test output pasted; review findings | `verify-before-done` (pm) · `/code-review` · `cross-review-gate` (library) |
| **Ship** | merge / deploy | — |
| **Learn** | incident or lesson → a new `docs/intent/` entry | (feeds back to Discover) |

**Small work** (fits one session) skips Chart → Ticket: Discover → Build → Verify → Ship. **Trivial edits** skip everything — just do them. **Bugs** → `/diagnosing-bugs` (failing test first), then Verify.

## Gate schedule

Review gates run at stage boundaries, never inside a stage. Discovery and grilling are gate-free — a gate on a half-formed thought produces noise. All three are `cross-review-gate` (library skill; Ringer panel where installed); only the artifact and the framing change.

| Boundary | Default? | Framing in the gate's `brief.md` |
|---|---|---|
| **Intent accepted** (end of Discover) | optional — the *pre-mortem* slot | "Assume this shipped and the client wasn't happy. Narrate how." Wrong problem, wrong outcome, wrong size. Correctness can't be judged yet; plausibility of failure can. |
| **Plan finalized** (grilling done, plan written) | **yes** | Is the plan sound; what's missing; which decision is most likely wrong. |
| **Chunk of code green** | **yes** | The usual: correctness, spec fidelity, standards. |

No separate pre-mortem skill — the framing sentence is the whole difference, and it belongs in the brief, not in a new skill.

## The one rule: `docs/` is shared record, `_pm/` is personal log

| | `docs/` | `_pm/` |
|---|---|---|
| Holds | intent, ADRs, `CONTEXT.md`, agent config (`docs/agents/`) | Intent-of-the-day, session entries, what I'm picking up |
| Authoritative? | **Yes** — with the tracker | **No** — a log; if it disagrees with the tracker, the tracker wins |
| Shared? | Yes — collaborators and clients read it | Per-person (`_pm/sessions/YYYY-MM-DD-<name>.md`), append-only |
| Written by | `discovery`, `/domain-modeling`, `/grilling`, `setup-matt-pocock-skills` | `whats-next`, `checkpoint`, `stepping-away` |

Decisions go to `docs/adr/` (Matt's home), not `_pm/`. Projects from pm ≤ 0.7 carrying `TASKS.md` / `_pm/decisions/` / `context-map.md`: see `MIGRATION-0.8.md`. Work items live on the tracker (GitHub Issues in a team; local markdown for solo/plugin repos), not in a task file. `_pm/` records *what I did and what I'm doing* — never *what is true*.

## Team model

Work → pm records the session → push the branch → the next person pulls and merges. Works because `_pm/` files are per-person and append-only (no conflicts) and nothing in `_pm/` is a state store. Trackers and `docs/` carry the shared truth across people and machines.

## Day shape

- **Morning** — `whats-next`: reads the tracker frontier + yesterday's session, proposes a pick-up, drafts today's Intent block.
- **Start of anything non-trivial** — `discovery`, then the size call decides the road.
- **Mid-session** — `checkpoint` on a consequential result; `/handoff` when a session outgrows itself.
- **Any completion claim** — `verify-before-done`: run it fresh, read it, paste it.
- **Stage boundary** — `cross-review-gate` per the gate schedule above (optional at intent, default at plan and at green chunks).
- **Close** — `stepping-away`: Intent vs shipped, session entry, durable knowledge routed to the library.

## Source

This doc is the workflow of record for DataCraft repos; the global `Agentic/CLAUDE.md` routing section points here. Intent behind the shape: `docs/intent/pm-workflow-reshape.md` in the dc-plugins repo (derived from Anthropic's *AI-Native SDLC Playbook* reviewed against the stack on 2026-08-23); the 0.10 lightening: `docs/intent/pm-010-lightening.md` (cross-review 2026-08-28).
