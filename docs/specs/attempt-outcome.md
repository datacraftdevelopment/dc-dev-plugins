# Spec: a ticket attempt that returns an outcome

Tracker entry: #36 (tickets #37, #38). Moved here from the issue body on 2026-10-10.

Candidate 3 of the 2026-10-09 Runway architecture audit. Interface settled with Joe; technical questions went through fast grill (Astra seat via Ringer: 6 agree, 1 disagree resolved, 1 one-way door answered by Joe).

## Problem

`run_ticket` (factory/plugin/runway/runway.py) has eight ways to end (lost claim, stopped, signed-out, question, agent failed, no commits, check failed, merge conflict, merged), and each one makes its own tracker write, run record, heartbeat, notify and worktree cleanup. The rules exist only as the order of the lines.

## Interface

```
run_ticket(cfg, root, tracker, t)
  claim, read the claim back        # lost claim: return, nothing settled
  outcome = attempt(cfg, root, t)   # git only
  settle(cfg, root, tracker, t, outcome)
```

- **Attempt**: makes the worktree, runs the agent and check with retries, merges into integration. Never touches the tracker, notify, or the outcome record. Returns `Outcome(kind, attempts, detail)`, one dataclass, `kind` one of `stopped`, `signed-out`, `question`, `agent-failed`, `no-commits`, `check-failed`, `merge-conflict`, `merged`.
- **Settle**: a table from kind to a row (ticket write: ready / needs-human / resolved; notify or not; record `result`; heartbeat `last_result` or none; remove worktree; remove branch) plus one `settle()` function. Note text per outcome is today's wording.

## Rules (all behavior-preserving)

- Live effects stay in the attempt: `run_agent`'s per-call run records, its auth pause and notify, per-attempt `fail` beats, `beat()` phases and `agent_pid` updates. Settle writes only the one outcome record.
- The outcome record keeps `result` values exactly as today (`done`, `needs-human`, `stopped`, `signed-out`); the Mac app and `runway retro` read them. A new `outcome` field carries the kind.
- Heartbeat: `merged` → pass; `stopped` and `signed-out` leave `last_result` alone; everything else → park.
- Cleanup: `stopped` keeps worktree and branch until the next run (Joe, 2026-10-09: keep as today; `test_pause.py` keeps checking it). Every other outcome removes the worktree and keeps the branch.
- A stop request still wins over an auth failure. Lost claim is not an outcome. Exceptions stay exceptions, no new try/finally.
- Settle keeps today's order: reload ticket, tracker write, notify, heartbeat, record, cleanup. The reload moves after the merge (today's code already merges before `mark_resolved`).
- Edge cases as today: a stop before the first call counts as attempt 1; record detail truncated to 500 chars, tracker note gets full text; `max_attempts <= 0` maps to `agent-failed` with "Agent run failed with no detail."

## Tests

Attempt: real temp repo (`make_repo()`), fake agent, no tracker. Settle: fake ticket, notify and record, no git. Existing end-to-end tests stay green unchanged.

## Related

Blocked by #7 (moves the engine). The ticket-protocol refactor ([ticket-protocol.md](ticket-protocol.md)) may rename the `mark_*` calls; if it lands first, settle calls the new names. The app's review-waiting-tickets work can flag parked tickets by `outcome`.
