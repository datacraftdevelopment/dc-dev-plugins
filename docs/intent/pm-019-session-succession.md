# PM lean orchestration and optional succession beta

Status: implemented and installed locally in Claude and Codex, 2026-09-14.
Joe approved the design in the plugin review conversation. See the
[review and verification record](../reviews/pm-019-fable.md).

## Intent

**Final direction, clarified during implementation:** reduce tiny-task ticket
overhead. Keep meaningful outcome tickets, one orchestrator, autonomous subagents,
proportionate verification and concise handoffs. The orchestrator can prepare
shared scaffolding and execute a dependency graph with **up to six active
subagents**, selecting ready branches and integrating prerequisite outputs before
downstream work. Graph nodes are worker assignments under a parent outcome,
not mandatory extra tickets. Four existing independent tickets can run together;
one large ticket can also have several independent worker assignments.

Manual `stepping-away` → fresh session → `whats-next` is already useful and stays
the default. Planning ceremonies, extra review rounds and parallelism require a
concrete uncertainty or useful independent work. Automatic succession remains
an explicitly opted-in experiment, evaluated by user effort saved. Preserve
existing project requirements, runtime grants and required evidence channels.

The implementation updates PM's default workflow, doctrine, session routing,
discovery/grill triggers and scaffold guidance; it adds one `orchestrate` entry
point reusing Ringer, not a new worker engine. Ringer base manifests have no DAG
dependency fields: dispatch only ready nodes in successive runs. A prepared real
ticket frontier may use build-swarm's own dependency-aware loop. Its native wave
default remains one; an explicitly screened PM wave may be up to six.

## Optional succession experiment

Maximize completed work without Joe's supervision. Preserve his rhythm of one or
two tickets per session and fresh context around 150,000–200,000 tokens. A session
finishes, leaves a compact handoff, starts one successor and retires. Parallelism
is optional, with at most three active sessions across both machines; the first
beta exercises a single chain, three sessions long, with no parallel spawning.

The SB-SOS and YoJoe pilots shipped work but did not establish net throughput:
6–8 sessions, a memory crash, reopening sessions and recovery cost Joe attention.
That pilot initially prioritized session succession. The final direction above
supersedes that priority: lean subagent orchestration is the default, while
automatic succession must demonstrate that it saves user effort.

Joe clarified during implementation: the active session is the orchestrator;
autonomous ticket work belongs to subagents through the existing Ringer /
build-swarm path. New sessions replace the orchestrator at context boundaries.
They are not the default worker mechanism. The orchestrator keeps decisions and
short reports, while worker investigation and execution stay in worker contexts.

## Accepted behavior

- Existing project requirements and grants remain binding. A separately recorded, explicit
  succession opt-in authorizes session creation, names the scope and bounds the
  run. It does not grant edits, commits, pushes, reviews or external actions;
  those inherit their existing authorization by reference.
- Select only ready, authorized, unclaimed work. Park needs-human tickets with
  their question and continue independent work; stop when none remains.
- Use bounded subagents for autonomous work. Finish or verifiably pause owned
  workers before turnover; successor creation is not work delegation. Worker
  failures become durable status, not additional interactive sessions for Joe.
- Check context at task boundaries. At 150k, rotate at a safe boundary; at 200k,
  stop expanding work and make a recoverable checkpoint. Without actual context
  telemetry, use the one-or-two-ticket fallback. Cumulative billing tokens are
  not context occupancy.
- Finish verification and close-out before preparing the next handoff. Preserve
  the next ticket, exact revision, authorization reference, essential decisions,
  verification references, blockers and first next action, not the transcript.
- Persist launch intent before invoking the host. One caller receives permission
  to dispatch. An ambiguous response remains pending until reconciled using the
  same launch marker; retries must not create duplicate successors.
- Record creation separately from successor acknowledgement. The successor opens
  its own session record, revalidates the ticket and authorization, acknowledges
  the handoff and waits. Only after the predecessor releases its own disposable
  resources and records retirement may the successor begin editing.
- Keep exact predecessor/successor identities and transition history. Reconcile
  interrupted handoffs from disk. A local helper cannot prove a remote session
  started, kill processes safely from a PID alone, or enforce a cross-machine cap.
- Host controls are read from the current tool contract. Unsupported startup,
  required clicks and unconfirmed archival are visible states, never simulated
  with an untracked background model process.

## Implementation

The existing session allocator remains the record identity authority. A separate
Python helper owns the succession state machine, with an atomic JSON record and
a filesystem lock in Git's common directory. All worktrees see one chain; this
beta uses the same checkout sequentially. A new skill owns host dispatch and
recovery; the three session skills link to it only for opted-in chains. Codex host
adaptation belongs in the builder. Runtime state is local; it is not an offline
distributed lock or a backup service.

## Verification and beta evidence

Automated checks cover concurrent launch reservation, uncertain creation,
successor identity, ordered ownership transfer, duplicate retries, stale revision
and authorization, session budget, and a three-session chain with interruption.
Run the existing session and plugin suites, build and validate the relocated PM
package, then install and compare both hosts' installed contents.

Actual host startup/click behavior is a live beta check, distinct from helper
tests. Each beta records completed tickets, user interventions, context source,
turnover failures, resource cleanup and recovery minutes. Success: two turnovers
without Joe restarting a session or restating the work.
