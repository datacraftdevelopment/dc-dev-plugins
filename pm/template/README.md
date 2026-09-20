# datacraft-Project

Project-management scaffold for this engagement. Light by design: only the
day-one folders exist; everything else is created on first use (the taxonomy
lives in `CLAUDE.md`).

## Working the project

1. `_pm/skeleton.md` holds the outcome, journey, and non-negotiables —
   written at scaffold time; keep it current as scope moves.
2. Use `orchestrate` for clear, authorized outcomes. Shared setup precedes a graph
   of up to six ready subagents; their assignments stay under the outcome ticket.
   Use `discovery` only when the outcome or scope still needs clarification.
3. Open each session with `whats-next`; close it with `stepping-away`.
4. Decisions go to `docs/adr/` when they need a durable separate record; meaningful
   work items live on the tracker. Tiny implementation steps don't need tickets.
5. Planning and extra review resolve named uncertainties. Keep genuine human
   questions together in the orchestrator, with their record on the affected ticket.
6. Use Sol for ordinary Codex sessions and Opus for ordinary Claude Code sessions.
   Astra and Fable are bounded Ringer review seats, invoked for a named risk rather
   than after every successful chunk. Either may lead an orchestrated run from a
   fresh session, manager-only.

Stamped by the pm plugin's `/pm:pm-scaffold` (`datacraftdevelopment/dc-dev-plugins`).
The workflow of record is that plugin's `WORKFLOW.md`.
