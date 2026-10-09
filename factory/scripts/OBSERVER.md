# Local observer pilot

Software Factory's completion contract is **ticket → implementation → independent
verification → merge or repair**. Matt Pocock's planning skills produce GitHub
tickets; Python dispatch keeps routine scheduling inexpensive. A zero process
exit or confident agent summary is not proof of completion.

`observe.py` reads this repository's Runway state and appended run records every
600 seconds (ten minutes), matching the verified Runway scheduler interval.
It writes only `_pm/observer/`: an atomic cursor plus retained packets,
a bounded JSONL projection, a lock, rotating logs, and its own check duration.
The initial source inode and byte boundary are persisted until its backlog is
drained across 500-record batches. Historical records remain `baseline: true`
across those batches; records appended after the initial boundary are new.
Detected rotation or truncation starts a new source generation and clears the
old historical boundary, including truncation that preserves the source inode.

Events cover completed prep calls, parked/failed work, finish results, failed or
held `verdict` rows, `merge` rows, pause or waiting transitions, and phases exceeding their configured time budget. An
overdue phase is a request to verify liveness, not proof of a dead process.
Normal successful ticket runs do not emit events. No model runs per poll.
Repeated waiting reasons are suppressed across ticks until the condition changes
or clears. The cursor handles partial records, truncation and inode rotation;
the latest 2,000 event identities are retained. The packet queue retains at most
the latest 1,000 packets and 2 MiB of serialized packet data, whichever fills
first. Older observer packets are evicted; Runway's original records and tracker
issues are untouched. Each event includes a local issue
draft with publishing disabled, the check command and an observed integration
head. For historical records that head is not proof of the failed commit: verify
it before publishing. No raw error/log excerpt is copied automatically.

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
repository, integer interval 30–3600 seconds (default 600), output `_pm/observer` unless `--out`
is passed directly to `observe.py`. Tracker publishing and merging are disabled.

From the source checkout:

```sh
python3 factory/scripts/observer_service.py preview --root /path/to/approved/repo
python3 factory/scripts/observer_service.py install --root /path/to/approved/repo
python3 factory/scripts/observer_service.py status --root /path/to/approved/repo
python3 factory/scripts/observer_service.py set-interval --root /path/to/approved/repo --interval 600
python3 factory/scripts/observer_service.py refresh --root /path/to/approved/repo
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

`set-interval` updates the matching observer's cadence and applies its bounded-log
routing, then reloads that observer. `refresh` applies log routing while retaining
the existing cadence. Both preserve scope, other plist fields and queue/cursor. The installed
`--interval` argument controls the polling sleep; `ThrottleInterval` is restart
throttling, not polling frequency. Runway's scheduler remains separate and was
verified configured at 600 seconds; this command never changes it. This matches
frequency, not exact clock phase, and does not automatically follow future
scheduler changes. Reverify the runner plist before choosing a new value.

## Persistence and retention

`state.json` is the authoritative atomic commit containing both the source
cursor and retained packets. `events.jsonl` is a replaceable projection, not an
append-only journal; consumers must use event IDs rather than byte offsets.
If projection writing fails after the state commit, the next check rebuilds it
without generating duplicate events. If the state write fails, neither cursor
nor queue advances. Files are flushed and fsynced before atomic replacement.
Legacy queues are imported and reconciled against existing event IDs on upgrade.

The daemon writes INFO/ERROR diagnostics through rotating handlers: each of
`service.log` and `service-error.log` is limited to 256 KiB plus two backups.
Messages are bounded; raw source records are never logged. launchd stdout/stderr
go to `/dev/null`, preventing a second unrotated log stream. `--once` still prints
new packets for interactive inspection. Startup/import errors before the logger
initializes must be diagnosed through launchctl status/exit information.

Uninstall tolerates a verified absent service (`launchctl print` reports error
113 and "Could not find service") and removes its plist. Other access/domain
errors are surfaced without removing the plist. This also permits recovery from
a failed bootstrap. No Runway plist, logs or user data is removed.

## Merge gate: Runway applies it, the observer watches

One contract. At finish Runway reviews the integration branch and writes a
`verdict` row to `_pm/runway-runs.jsonl` (verdict, blocking findings, criteria,
`hold`, reviewed `sha`, per-seat provenance). What the engine now owns, so
nobody repeats it by hand: the full check after the last edit, the independent
review panel with the reviewed SHA on every seat, the pass/fail call, the fix
ticket on a fail, and the merge itself.

`merge` in `runway.json` has three modes:

| Mode | Engine does |
|---|---|
| `off` | Verdict only. Joe merges the integration branch. |
| `shadow` | Verdict, plus a fix ticket on a fail. Never merges; says "would merge" on a pass. |
| `on_pass` | Same, and a pass with no `hold` merges the reviewed SHA into base. A moved head merges nothing. |

**This repo is in `shadow`**: Runway reports and files fix tickets, and Joe
(or the assistant, on Joe's go) still does the integration-to-main merge.

The observer turns these rows into events, with no model per poll:

- `verdict` that failed, or passed but was held for Joe. A fail means Runway
  filed (or commented on) a fix ticket; the row has no ticket id, so find it
  under the original issue. A clean pass is a normal run and emits nothing.
- `merge` (only in `on_pass`): Runway merged the reviewed SHA into base.

What the engine still does not cover, and stays with the assistant:

- Behavioral/end-to-end evidence for user-facing or integration behavior. The
  verdict is a diff-and-check review. Missing access or an unverified
  requirement is blocked.
- Consequential findings resolved or explicitly accepted by the user.
- In `shadow`/`off`, the final merge. Recheck the head against the verdict's
  `sha`, plus migration/marketplace impact and human gates, immediately before it.

Do not restart Runway, merge, delete branches or publish releases from observer
events, and do not bypass protections. A failed second round parks the fix
ticket for triage; do not spend tokens looping.

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

Existing #21–#23 cover the discovered blockers; do not file duplicates. They
depend on #7; verify its current approval and completion before dispatching
repairs that assume a new engine location. Installed-plugin migration #8 is not approved
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

Operational update: another workflow merged PR #20 at 2026-10-09 08:31 UTC
as `1eee58cfa7d05cd39ccf3e5b1991a172d9e78f22`. This observer/assistant pilot
did not perform that merge or establish replacement green-check evidence.
Runway subsequently synced main into integration and started approved #6;
#7 also carries an approval. Preserve its repair queue rather than dispatching
competing implementations. This supersedes PR #20 as a pending pilot candidate.

At the next observation, #6 completed, #7 parked because the worker's allowed
tools did not permit `git mv`/backup, and #18 started. The observer does not change
that permission gate. #21–#23 remain behind #7 until a scoped authorization
or other approved resolution unblocks it.
