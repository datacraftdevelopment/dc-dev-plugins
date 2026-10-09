# Glossary

## Runway engine (`pm/runway/runway.py`)

**Attempt**: one pass at building a ticket: a fresh worktree, then the agent/check retry loop, then the merge into the integration branch. `attempt(cfg, root, t)` runs it and returns an Outcome. It never touches the tracker, `notify` or the outcome `record`; `run_ticket` hands the Outcome to Settle. Not to be confused with a single agent call inside the loop, which is also numbered "attempt" in records and logs.

**Outcome**: how an Attempt ended: `Outcome(kind, attempts, detail)`. `kind` is one of `stopped`, `signed-out`, `question`, `agent-failed`, `no-commits`, `check-failed`, `merge-conflict`, `merged`. `attempts` is how many agent calls were started, and `detail` is the text a human needs (empty when there is none).

**Settle**: what Runway does with an Outcome. `settle(cfg, root, tracker, t, outcome)` looks the Outcome kind up in the `SETTLE` table (ticket write, notify or not, `result`, heartbeat `last_result`, remove worktree, remove branch) and does it in one order: reload the ticket, write the tracker, notify, heartbeat, record, clean up. The outcome row in `_pm/runway-runs.jsonl` keeps `result` (`done`, `needs-human`, `stopped`, `signed-out`) and carries the Outcome kind in `outcome`.
