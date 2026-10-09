# Glossary

## Runway engine (`pm/runway/runway.py`)

**Attempt**: one pass at building a ticket: a fresh worktree, then the agent/check retry loop, then the merge into the integration branch. `attempt(cfg, root, t)` runs it and returns an Outcome. It never touches the tracker, `notify` or the outcome `record`; `run_ticket` hands the Outcome to Settle. Not to be confused with a single agent call inside the loop, which is also numbered "attempt" in records and logs.

**Outcome**: how an Attempt ended: `Outcome(kind, attempts, detail)`. `kind` is one of `stopped`, `signed-out`, `question`, `agent-failed`, `no-commits`, `check-failed`, `merge-conflict`, `merged`. `attempts` is how many agent calls were started, and `detail` is the text a human needs (empty when there is none).

**Settle**: what Runway does with an Outcome. `settle(cfg, root, tracker, t, outcome)` looks the Outcome kind up in the `SETTLE` table (ticket write, notify or not, `result`, heartbeat `last_result`, remove worktree, remove branch) and does it in one order: reload the ticket, write the tracker, notify, heartbeat, record, clean up. The outcome row in `_pm/runway-runs.jsonl` keeps `result` (`done`, `needs-human`, `stopped`, `signed-out`) and carries the Outcome kind in `outcome`.

**Ticket protocol**: the rules every tracker shares, written once in `pm/runway/ticket_protocol.py`: gate, status, is_spec, harness, claimed_by, packet, the ticket `text`, the park / approve / decline / release / packet wording, `sync`'s go and drop rules, and the once-only log. The engine only ever sees the ticket interface it builds. Where GitHub and Linear still differ (the go note, the park wording, the trust rule, the write order) the difference is a named switch in `Rules`, not a second copy of the code.

**Adapter**: one tracker's side of the Ticket protocol, in `github_tracker.py` and `linear_tracker.py` (and `test/memory_adapter.py`, the in-memory one the tests use). It keeps only *facts* (`closed`, `held`, `has_children`, `blocked_by`, and the id, title, url, body, labels and comments it reads) and *writes* (`_post`, `_claim`, `_close`, `_release`, `_relabel`, `_create`), plus its own transport, pagination, retries and `setup`. It never decides what a ticket's gate or status is, or what Runway says.
