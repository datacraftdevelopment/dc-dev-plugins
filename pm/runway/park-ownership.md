# Park ownership and rollout

GitHub and Linear do not provide conditional lifecycle writes in these adapters.
A fresh read, a machine claim, and a local lock cannot elect an exclusive writer
across Macs. This protocol therefore requires an operator-designated **single
writer root for the entire tracker scope** (GitHub repository or Linear project).
All other roots observe only. This intentionally gives up concurrent cross-Mac
work on that scope until a stronger coordination mechanism exists.

## Required configuration

Every runner targeting the same scope must carry the **same** `park_authority`
UUID inside its `github` or `linear` object in `runway.json`. This is a non-secret
root identity, stored locally in `_pm/park-owner`; preflight initializes that
identity and waits when authority is absent or does not match. Do not clone this
file while its original root can run. Worktrees are not independent writers.
Missing, malformed, or mismatched designation prevents claims, lifecycle writes,
and tick/finish model calls. Corrupt local recovery state also fails closed.
Read-only status remains available. The markdown tracker is local and unchanged.

**This is an operational prerequisite, not a distributed lock.** Conflicting
configuration on two roots, cloned identities, older binaries, direct adapter
writes, or external tracker administration cannot be fenced by these APIs. If
you cannot establish one exclusive writer, leave authority unset and do not run.
There is no automatic election, lease expiry, or takeover.

## Rollout and deliberate handoff

1. Stop and verify shutdown of every existing runner for the tracker scope,
   including scheduled jobs and manual sessions. Older versions ignore the
   shared barrier and must not coexist with this version.
2. Inventory outstanding local journals and shared intents. Legacy records
   without an operation ID or owner require manual resolution while stopped;
   the engine never adopts them automatically.
3. Choose one existing root identity, configure that same designation in every
   participating project checkout, and start only the designated root. Verify
   every other root reports waiting before enabling schedules.
4. If the owner disappears, recovery remains blocked. A human must verify the
   old owner cannot resume before resolving/transferring unfinished operations
   and changing the designation consistently everywhere. No handoff command is
   provided. If shutdown or configuration consistency cannot be verified, wait.
5. Tracker administration that changes lifecycle or approvals likewise requires
   stopping the owner first. Never resolve an ambiguous intent by guessing.

## Safety boundary

Creation and reconciliation use the same local per-ticket lock. Creation reloads
and resumes an existing owned intent, refuses a foreign intent, and rejects
stale claim generations or completed parks awaiting fresh approval. The intent
(UUID, owner, full note) is journaled and published before lifecycle changes.
A separate local journal lock and atomic replacement preserve other tickets.
Reconciliation reloads under lock and rejects completed/superseded UUIDs before
writes; cleanup is conditional on UUID. A local intent that failed to publish
blocks new claims and approvals until the owner republishes it.

An unfinished park blocks approval. Completion invalidates earlier go comments
and labels; only fresh trusted go after completion is consumed into an Approved
note. A subsequent terminal drop stays resolved. Delayed recovery cannot undo
that fresh approval or a new claim. Locks assume a local filesystem with flock;
network filesystem coordination is unsupported.
