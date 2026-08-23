# WORKFLOW — how pm fits around the Matt-primary stack

The engine is Matt Pocock's skill set (`/wayfinder`, `/grilling`, `/domain-modeling`, `/prototype`, `/research`, `/to-spec`, `/to-tickets`, `/implement`, `/tdd`, `/code-review`, `/handoff`). **pm fits around its structure, never the reverse.** pm is exactly three things:

1. **The on-ramp** — `discovery`: riff until the shape is visible, write `docs/intent/<slug>.md`, make the size call.
2. **The session layer** — `whats-next` · `checkpoint` · `stepping-away`: per-person, append-only logs in `_pm/`. Never authoritative.
3. **The visibility layer** — `dashboard`: a stage board derived from artifacts. Local-only render.

Anything else in pm has to justify itself or get deleted.

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

## The one rule: `docs/` is shared record, `_pm/` is personal log

| | `docs/` | `_pm/` |
|---|---|---|
| Holds | intent, ADRs, `CONTEXT.md`, agent config (`docs/agents/`) | Intent-of-the-day, session entries, what I'm picking up |
| Authoritative? | **Yes** — with the tracker | **No** — a log; if it disagrees with the tracker, the tracker wins |
| Shared? | Yes — collaborators and clients read it | Per-person (`_pm/sessions/YYYY-MM-DD-<name>.md`), append-only |
| Written by | `discovery`, `/domain-modeling`, `/grilling`, `setup-matt-pocock-skills` | `whats-next`, `checkpoint`, `stepping-away` |

Decisions go to `docs/adr/` (Matt's home), not `_pm/`. Work items live on the tracker (GitHub Issues in a team; local markdown for solo/plugin repos), not in a task file. `_pm/` records *what I did and what I'm doing* — never *what is true*.

## Team model

Work → pm records the session → push the branch → the next person pulls and merges. Works because `_pm/` files are per-person and append-only (no conflicts) and nothing in `_pm/` is a state store. Trackers and `docs/` carry the shared truth across people and machines.

## Day shape

- **Morning** — `whats-next`: reads the tracker frontier + yesterday's session, proposes a pick-up, drafts today's Intent block.
- **Start of anything non-trivial** — `discovery`, then the size call decides the road.
- **Mid-session** — `checkpoint` on a consequential result; `/handoff` when a session outgrows itself.
- **Any completion claim** — `verify-before-done`: run it fresh, read it, paste it.
- **Stage boundary** (plan finalized, chunk green, migration drafted) — `cross-review-gate`.
- **Close** — `stepping-away`: Intent vs shipped, session entry, durable knowledge routed to the library.

## Source

This doc is the workflow of record for DataCraft repos; the global `Agentic/CLAUDE.md` routing section points here. Intent behind the shape: `docs/intent/pm-workflow-reshape.md` in the dc-plugins repo (derived from Anthropic's *AI-Native SDLC Playbook* reviewed against the stack on 2026-08-23).
