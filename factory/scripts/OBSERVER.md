# Local observer pilot

Software Factory's completion contract is **ticket → implementation → independent
verification → merge or repair**. Matt Pocock's planning skills produce GitHub
tickets; Python dispatch keeps routine scheduling inexpensive. A zero process
exit or confident agent summary is not proof of completion.

`observe.py` reads this repository's Runway state and appended run records every
30 seconds. It writes only `_pm/observer/`: an atomic deduplication cursor,
bounded event packets, a lock, and its own check duration. The first scan marks
historical records as `baseline: true`; they are not new incidents.

Events cover completed prep calls, parked/failed work, finish results, pause or
waiting transitions, and phases exceeding their configured time budget. An
overdue phase is a request to verify liveness, not proof of a dead process.
Normal successful ticket runs do not emit events. No model runs per poll.

The scoped LaunchAgent `com.joe.runway.observer.dc-dev-plugins` runs only this
observer; it does not replace or restart Runway. Check it with
`launchctl print gui/$(id -u)/com.joe.runway.observer.dc-dev-plugins`.
Its logs and event queue are under `_pm/observer/`. A one-shot check is:

```sh
python3 factory/scripts/observe.py --root . --once
```

This local queue does **not** wake a Codex conversation. No callback, credentials,
connector subscription, or AI schedule is configured by this pilot. A supported
wake-up route must be separately connected and verified before claiming
continuous assistant supervision. It does not query GitHub for unrelated new PRs.

The observer cannot merge. The one-candidate merge pilot requires a fresh review
of the exact head, acceptance evidence and a green full check. Runway's internal
ticket-to-integration merges are separate from the final integration-to-main
merge. Human migration/product decisions remain pending.

## Installation and recovery

Source, tests and operating instructions live in this repository. The example
`observer-config.example.json` describes the configuration; it is documentation,
not an automatically loaded file. CLI arguments are authoritative: one explicit
repository, integer interval 30–60 seconds, output `_pm/observer` unless `--out`
is passed directly to `observe.py`. Tracker publishing and merging are disabled.

From the source checkout:

```sh
python3 factory/scripts/observer_service.py preview --root /path/to/approved/repo
python3 factory/scripts/observer_service.py install --root /path/to/approved/repo
python3 factory/scripts/observer_service.py status --root /path/to/approved/repo
python3 -m unittest discover -s tests -p test_runway_observer.py -v
```

Installation writes one user LaunchAgent using the current Python interpreter
and absolute source path. Keep that checkout available. Existing observer
configuration is preserved. For recovery, inspect `service-error.log` and
`state.json`, confirm the source path exists, and explicitly uninstall/reinstall
the observer if needed; do not restart Runway. Uninstall uses
`observer_service.py uninstall --root /path/to/approved/repo`. Queue and cursor
remain for audit. The source is outside `factory/plugin` and is not distributed
by marketplace installation yet.

## Independent completion and merge gate

For the one-candidate pilot, prepare a bounded evidence packet containing:

- Original ticket and acceptance criteria; map each criterion to evidence.
- Exact candidate SHA, base SHA and relevant diff; recheck before merging.
- Relevant tests plus the full repository check, executed after the last edit.
- Behavioral/end-to-end evidence for user-facing or integration behavior when
  applicable. Missing access or an unverified requirement is blocked.
- Fresh independent review artifacts with run ID, SHA, time and reviewer identity.
  Reused output, stale reports and successful report-format checks do not count.
- Consequential findings resolved or explicitly accepted by the user.

Permit one scoped repair attempt and repeat verification of its changed head;
if that attempt fails, retain a durable issue and stop for triage rather than
repeatedly spending tokens. Do not restart, merge, delete branches or publish
releases from observer events. Do not bypass protections. Final integration-to-
main merging remains an assistant action after these checks; successful ticket-
to-integration merges inside Runway are separate. Recheck migration/marketplace
impact and human gates immediately before the final merge.

## Failure ownership and tracker records

Current ticket failures call `mark_needs_human` on the original ticket. The
GitHub/Linear adapters post bounded failure details and park the ticket. They
do not create separate factory bugs. Finish failures write review/PR/log artifacts
and a finish record and can still create a draft PR. The October 9 finish created
PR #20 with check exit 1.

The assistant owns triage and follow-through. A failed job updates its original
issue; a factory defect gets a linked bug. Record exact head, failing command,
concise error, attempt history and evidence pointers. Deduplicate by repository,
head, check and failure signature; append repeated evidence to the same issue.
Keep private logs local; scrub excerpts before publication. Human product/risk
decisions remain pending. This observer has no tracker publishing adapter.

Existing #21–#23 cover the discovered blockers; do not file duplicates. Their
dependency on human-gated #7 must be resolved before dispatching repairs that
assume a new engine location. Installed-plugin migration #8 is not approved
by a green check or approval of routine bug repairs.

## Usage measurements and delivery limits

Observer polls invoke no models. `state.json` records elapsed local check time.
Runway's JSONL records expose harness tokens/cost when available: separate coding,
review, repair and PR generation. Ringer panel records currently expose seat
status and elapsed time, not token counts. Unavailable telemetry is not zero.
Parent-assistant tokens are not exposed locally; do not estimate from prose length
or inspect restricted session stores.

Baseline: PR #20 at `4a27c7433568d00b8fa6286aa25074326ea54231`, failed full
check and stale Claude-seat report; no final merge eligible. GitHub main had no
protection, rulesets, Actions workflows or repository webhooks at inspection.
Future verification must not assume those settings remain unchanged.

A supported PR-event wake-up route may be possible with the official GitHub
plugin after connection, permission checks and event-schema discovery. It is
not installed/configured/verified by this observer. A filesystem watcher alone
cannot invoke this conversation. Local readiness and end-to-end AI supervision
must be reported separately.
