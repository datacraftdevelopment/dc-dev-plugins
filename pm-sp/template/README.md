# datacraft-Project

Project-management scaffold for this engagement. Light by design: only the
day-one folders exist; everything else is created on first use (the taxonomy
lives in `CLAUDE.md`).

## Working the project

1. `_pm/skeleton.md` holds the outcome, journey and non-negotiables, written at
   scaffold time; keep it current as scope moves.
2. Open each session with `whats-next`; close it with `stepping-away`.
3. New work: shape it with Agent Runway's skills (`grill`, `prototype`, then
   `spec`, which writes `docs/specs/` with its Acceptance checks), then build
   it in the session with the `hands-on` skill. Only a repo added to Runway
   can send it to the Runway app (one ask, kept as `runway: yes|no` in the
   spec); `ship-acceptance` proves the whole of it against production.
4. Decisions that need their own record go to `docs/adr/`. Loose ideas go to
   `docs/inbox.md`.

Stamped by the pm-sp plugin's `/pm-sp:scaffold` (`datacraftdevelopment/dc-dev-plugins`).
The workflow of record is that plugin's `WORKFLOW.md`.
