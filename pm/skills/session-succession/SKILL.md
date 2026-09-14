---
name: session-succession
description: "Opt-in beta: keep one orchestrator lean, delegate autonomous tickets to subagents, and replace the orchestrator with a fresh session at task/context boundaries. Use for an authorized succession handoff, an interrupted turnover, or a request to continue through fresh sessions."
---

# Session succession beta

One active **orchestrator session**, autonomous work in **subagents**, and a fresh
orchestrator when context fills. Optimize completed work minus user intervention
and recovery cost. Session creation is turnover, not the worker mechanism.

Manual `stepping-away` → fresh session → `whats-next` remains the default. This
experiment is optional; it earns retention only by reducing restarts, supervision
and recovery. It does not require smaller tickets or a new session per worker.

This skill is opt-in. Read the project's recorded succession permission and its
existing execution authorization. Installing PM does not opt a project in. A
request to implement this plugin does not authorize launching a client beta.

## Start or recover

1. Run the helper's `status` before starting or recovering a chain:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/succession.py" --root . status
   ```

   Use `state_path`, `runtime_dir`, `chain_id`, exact PM session path/ID and actual host session
   ID throughout. A missing chain is different from corrupt state or the wrong
   checkout; preserve errors and reconcile them. Never choose the newest session
   file. State lives in Git's common directory; linked worktrees share the lock.
   This beta runs successors sequentially in the **same checkout**. It does not
   coordinate offline replicas or automatically migrate machines.

2. For a new opt-in, record the user's authorization and the policy from
   [protocol.md](protocol.md#opt-in). Reuse existing permission; ask only for a
   genuinely missing scope or action. Open/bind this session with `whats-next`,
   then `start`. Default run budget: three sessions total, including this one.
   That budget bounds this beta, not the context window. Renew it only on the
   user's instruction. The active-session ceiling is three across both machines;
   the first beta uses one chain with no additional worker sessions. Inspect the
   available host inventory; if the cross-machine count is unknown, surface it
   before dispatch rather than claiming the local lock enforces it.

3. If state exists, follow [protocol.md](protocol.md#recovery) for its phase.
   Continue the bound chain; an ambiguous launch is never a reason to start over.

## Work inside the orchestrator

Read the bound intent, tracker and existing authorization. Pick a ready,
authorized, unclaimed ticket and claim it on the tracker **before dispatch**.
Use [orchestrate](../orchestrate/SKILL.md) for the work graph and its ceiling of
six active subagents. It owns shared setup, ready-frontier dispatch, resource
screening, verification and worker briefs under the outcome ticket. Load Ringer
or build-swarm for the applicable transport/control mechanics. This beta grants
no additional review or build permissions.

Give workers a bounded ticket, source references and a completion check. Retain
short results and evidence links in the orchestrator; worker transcripts stay
outside its context. The orchestrator selects, integrates, verifies and records
work. A ticket needing Joe's decision stays with the orchestrator, with the exact
question recorded as `Waiting on:` / `needs-human`; select independent ready work
while it waits. If none remains, close and stop with one consolidated report.
Do not spawn another interactive session to deal with a blocked worker.

## Decide at a boundary

After a completed ticket, use the helper's `boundary` command. Supply actual
current context occupancy if the host exposes it, never billed/cumulative tokens.
With no occupancy signal, omit it and report `ticket-fallback`: one ticket can
continue; two completed tickets rotate. At 150k–200k, rotate at the next safe
boundary. Above the range, stop taking new work and make a recoverable checkpoint.
An unsafe boundary returns `checkpoint`, not permission to drop work mid-flight.

Finish or verifiably pause owned workers using their run controls before rotating.
Collect reports, integrate completed patches and verify the resulting revision.
Record paused work and ownership on the tracker so the successor cannot duplicate
it. A PM close marker does not stop a worker. Leave lengthy evidence in files.

## Turn over

1. Select and reserve the next ready ticket within the approved scope. If no work
   is ready or the run budget is exhausted, run `stepping-away`, release owned
   disposable resources, and `stop`; do not create a successor.
2. Run `stepping-away` for this session. Finish authorized close-out and commits
   before `prepare`. An unfinished large outcome can continue across sessions
   after a verified, recoverable checkpoint; it does not need another ticket.
   Retain the reserved next ticket for the successor; ordinary
   session close must not unclaim it. Write the compact JSON brief **inside the
   reported `runtime_dir`**, described in
   [protocol.md](protocol.md#handoff). Include the review baseline as a decision
   when WIP commits mean a review must cover more than the uncommitted diff.
3. Check the host's current creation/status controls and active-session budget.
   Follow [host.md](host.md). Prepare the complete launch prompt before reserving
   launch. `launch` persists the attempt and returns `dispatch_allowed`; **only
   the caller receiving true may make the one creation call**. Pass the chain ID,
   launch attempt, checkout and policy references to the fresh session. Transfer
   the brief and source pointers, not a fork of the full conversation.
4. Record the host's creation receipt with `created`. A chip, queued request or
   returned ID proves creation only. Report any required click. Wait boundedly
   for the successor's acknowledgement while remaining responsive to the user.
   If pending, report that status and preserve it for recovery. Do not poll forever
   or manufacture a running acknowledgement on the successor's behalf.
5. Once acknowledged, stop only this session's identified disposable servers and
   processes, using their own handles and controls. Verify stoppage and save a
   resource-release receipt inside `runtime_dir`; explicitly list any paused durable run. Avoid broad
   process-name kills. Then `retire`. Finish with the successor link and stop
   taking work; use a supported host close/archive operation if available.
   Logical retirement, archival and process exit are separate facts: report only
   what is confirmed. Archiving alone does not prove RAM was released.

## Receive the handoff

Read `status` by the supplied chain ID and match the launch attempt. Read the
referenced authorization, actual next ticket, revision and brief. Confirm that
the ticket is still ready and reserved for this chain. If it isn't, report the
conflict to the predecessor and use the recovery path; don't silently take a
different ticket. `whats-next` uses this named task without another pick round.
Open a fresh PM session record and run `acknowledge` with **your own** actual host
ID and bound PM identity. Until `retired`, wait; do not edit code, commit or launch
workers. After `retired`, run `begin`, transfer the tracker claim to this session,
and resume orchestrating subagents. If the parent is gone, retirement requires
observed resource release, not an elapsed timeout; see recovery.

## Beta evidence

Append a small table to the session close: tickets completed, worker runs,
decisions waiting on Joe, user interventions, context occupancy or fallback,
handoff outcome, owned-resource cleanup, recovery minutes. Unknown is acceptable;
invented numbers are not. The first live test is three sequential orchestrators,
with subagent work inside them and one interrupted handoff. Success means two
turnovers without Joe restarting or re-explaining work. Helper tests establish
state-machine behavior; live host startup and memory behavior need beta evidence.
