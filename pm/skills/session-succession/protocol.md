# Succession protocol

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/succession.py" --help` for flags.
`--root` always names the recorded project checkout; the helper never changes
branches, touches client systems, launches a model or stops processes itself.
The agent checks readiness/authorization and performs host actions; the helper
records those attestations and enforces transition ordering and identity.

## Opt-in

After explicit permission to continue through fresh sessions, write a project
policy (for example `docs/intent/succession-beta.json`) and retain the user's words
in the referenced intent. This policy is separate from `dc-autonomy-v1` and does
not enlarge its action grants. Match scope and limits to the user's request.

```json
{
  "policy": "dc-succession-beta-v1",
  "approved": true,
  "scope": "The accepted intent's ready implementation tickets",
  "max_sessions": 3,
  "allow_create_successor": true,
  "authorization_ref": "docs/intent/accepted-work.md"
}
```

The reference must include or point to the existing work permissions and explicit
successor-creation permission. Local helper validation checks shape and detects
file changes; it cannot infer consent from an `approved` Boolean. The agent must
verify it against the user's instruction. Hashes pin the policy and referenced
file for this chain. An authorization change blocks further work/launches, but
still allows recording creation, resource release or cancellation for recovery.
After cancelling/stopping, revalidate the changed permission before a new start.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/succession.py" --root . start \
  --policy-file docs/intent/succession-beta.json --host claude \
  --actor <actual-host-session-id> --session <bound-session-path> --id <bound-pm-id>
```

On Codex use `--host codex`. PM record UUIDs, host session IDs and launch attempt
UUIDs are distinct. CLI placeholders must be replaced with quoted actual values.
A repeat `start` returns the same active chain only for the same binding/policy.
Another worktree cannot start a second chain in this repository. A stopped chain
is archived in the common Git directory when an explicitly authorized new one
starts. These files are local recovery state, not a cross-machine registry.

## Boundary

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/succession.py" boundary \
  --tickets-completed 1 --context-tokens 160000 --safe-boundary
```

Omit `--context-tokens` when actual occupancy is unavailable; omit
`--safe-boundary` while a worker, integration or verification is unfinished.
`checkpoint` means make the current work recoverable first, then re-evaluate.

## Handoff

Write brief and receipt inputs inside the **`runtime_dir` returned by `status`**
(Git's common directory, outside tracked project content). Use its absolute path;
this also works when the common directory is outside a linked checkout. The helper
rejects inputs elsewhere. Leave ordinary `_pm/sessions/` records tracked according
to project convention. Do not add a blanket `_pm/` ignore to make turnover pass.
Do not write into the helper's `state.json`, `lock` or archived chain files.

Write a compact brief file there; the helper snapshots it into state (12,000 character
maximum). Evidence stays in source files; never embed credentials or transcripts.
Use the exact current commit hash, and commit authorized project/session changes
before preparation. The helper requires a clean checkout, except for the receiving
session's own newly allocated record during acknowledgement/begin.

```json
{
  "ticket": "docs/tickets/next-ticket.md",
  "revision": "<exact current commit hash>",
  "summary": "Previous ticket passed its checks and is recorded on the tracker.",
  "decisions": ["Preserve the accepted API; review from the recorded base commit."],
  "verification": ["docs/evidence/previous-ticket.md"],
  "blockers": ["Other ticket waits for Joe's copy decision; this ticket is independent."],
  "next_step": "Read this ticket and its acceptance check, then dispatch its worker."
}
```

`blockers` records parked *other* work. The next ticket itself must be ready.
It may be the same unfinished outcome across multiple context boundaries; the
brief identifies its verified checkpoint and next ready worker nodes.
Its tracker claim belongs to the chain until `begin` transfers it to the successor.
Each command below also takes `--root <checkout>` before the command name:

| Command | Required arguments after command | Meaning |
|---|---|---|
| `prepare` | `--chain ID --actor PARENT --brief-file FILE` | Closed predecessor, budget and clean revision checked; brief saved. |
| `launch` | `--chain ID --actor PARENT` | First caller alone gets `dispatch_allowed: true` and a durable attempt UUID. |
| `created` | `--chain ID --actor PARENT --attempt UUID --successor HOST_ID` | Record actual creation receipt; preserves a later acknowledgement. |
| `acknowledge` | `--chain ID --actor CHILD --attempt UUID --session PATH --id PM_ID` | Successor records its own identity/readiness; can recover a lost creation receipt. |
| `retire` | `--chain ID --actor PARENT --evidence-file FILE` | After acknowledgement and observed resource release, relinquish ownership. |
| `begin` | `--chain ID --actor CHILD` | Only after retirement: successor becomes active owner. Repeat is harmless. |
| `stop` | `--chain ID --actor CURRENT --reason TEXT` | Close a chain with no outstanding launch; requires a closed PM session record. |
| `status` | optional `--chain ID` | Read authoritative state, identities, history and timestamps. |

Retirement evidence names owned worker/server handles, stop or pause results,
and any durable paused runs with tracker ownership. If none existed, say how that
was checked. It is operator evidence, not an automatic process-inspection result.

## Recovery

| Phase | Next safe action |
|---|---|
| `active` | Resume the exact bound session; reconcile its ticket and workers first. |
| `prepared` | Revalidate readiness and host capability, then reserve launch. |
| `launching` | Search the host for the exact attempt marker; reconcile creation or let the real successor acknowledge. Do not call create again. |
| `created` | Open/check the recorded successor. A required start click remains a user blocker. |
| `acknowledged` | Successor waits; predecessor verifies resource release and retires. |
| `retired` | Successor can `begin`; predecessor takes no further work. |
| `stopped` | Show the stop reason and unresolved questions. No automatic budget renewal. |

A recovered controller may act for the predecessor only after the host confirms
the old controller is stopped and the recorded worker/server handles are released
or verifiably paused. Record that observation with the retirement evidence. Keep
the recorded predecessor ID when completing its transition; don't impersonate a
live predecessor or claim a timeout proves death.

If a creation call definitively failed *without creating anything*, record the
host's failure/absence evidence and use `not-created --chain ID --actor PARENT
--attempt UUID --evidence-file FILE`. Only then may a new `launch` issue a new
attempt. Inability to find a session in a partial inventory is not proof of absence.

If the successor exists but cannot proceed (changed scope/revision, cancellation,
or bad handoff), first stop it using supported host controls and verify stoppage.
Then `cancel --chain ID --actor PARENT --attempt UUID --evidence-file FILE` closes
the chain with that evidence. Reconcile the reserved tracker claim and any opened
successor PM record. Resume/restart only under the user's existing authorization
and remaining agreed budget; cancelling does not grant another batch of sessions.

State writes use a local exclusive lock and atomic replacement. This prevents
concurrent local reservations, not duplicate external creation after a dishonest
absence claim. Never reset/delete the state file to bypass a pending handoff.
