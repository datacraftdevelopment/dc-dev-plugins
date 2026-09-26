---
name: orchestrate
description: "Execute an outcome through bounded subagents: prepare shared scaffolding, dispatch ready nodes of a dependency graph (up to six active workers), then integrate and verify. Use for authorized implementation or independent ticket work; worker assignments stay under the outcome ticket."
---

# Orchestrate

One session owns the outcome, integration and Joe's questions. Workers do bounded
autonomous work through Ringer. Manual session rotation is normal; succession is
a separate opt-in experiment. Read [WORKFLOW.md](../../WORKFLOW.md) for scope,
conditional stages and the lead-seat rule.

**Context budget.** The orchestrator's own context is the largest cost of a run:
every call re-reads it. Start an orchestrated run in a **fresh session from a
written brief** (accepted scope, tickets, decisions, authorization), not inside
the discovery session. Read Ringer's summary table and result files by path; do
not stream run output into the session. Read diffs by path, not whole files.
Past about **150K** tokens of context, rotate at the next wave boundary: a
manual fresh session from a handoff.

## 1. Frame the outcome

Read the user's request, accepted intent and existing ticket(s). Use their current
authorization. A useful outcome is the ticket; scaffolding, files, tests, reviews
and worker assignments are steps inside it. Create additional tickets only for
separately useful outcomes, independent ownership or durable unresolved work.
Do not run `/to-tickets` merely to feed a worker engine. A small direct request
may be completed without a new ticket or delegation overhead.

**Size floor.** Work under about an hour of solo effort is not its own worker.
An Opus or Sol orchestrator does it directly. A review-tier lead seat (Astra or
Fable) is **manager-only**: it writes briefs, acceptance tests, checks,
manifests, tracker entries and integration commits, and batches small fixes
into one cheap worker instead of writing product code itself.

Record the target result and how it will be checked in the parent ticket or the
existing session brief. Settle only missing decisions that affect execution.
Preserve declared acceptance channels and required project checks.

## 2. Prepare the graph

The orchestrator may build shared scaffolding, settle interfaces and commit an
authorized baseline before dispatch. Keep a compact table in the parent record:

| Node | Output / owned paths | Requires | Verification |
|---|---|---|---|
| Setup | Shared types and fixtures | — | Baseline checks |
| A | One independent implementation part | Setup | Its focused check |
| B | Another independent part | Setup | Its focused check |
| C | Work consuming A's output | A | Consumer/contract check |
| Integrate | Combined outcome | B, C | Integrated acceptance checks |

This is a dependency graph, not a required topology or a second ticket system.
Some jobs have one node, some six ready branches, others several stages. Check
dependencies, shared interfaces/files and side effects: databases, credentials,
ports, deployments, hooks and shared documents. Resolve a shared contract in
Setup or serialize its writers. Keep tracker/changelog/client updates with the
orchestrator. A worker finding a new dependency returns it for re-planning.

Order nodes by risk, not size: the first code node is the skeleton that settles
the shape, the second is one deliberately small slice through it, and wider
nodes are released only after those two have passed their checks.

For code nodes, write the **acceptance tests before dispatch**. Run them against
the base to see them fail for the right reason. The node's check copies them
into the worktree fresh on every run, so a worker cannot edit them. Baseline
every check against an untouched tree before spending a worker on it.

Read `docs/agents/worker-env.md` when the repo has one; write it on the first
orchestrated run when it doesn't. It names what a fresh worktree lacks
(dependencies, generated types, local databases), the repo's own verify command
that makes a worktree runnable, the commands the worker lane allows, off-limits
paths and the supported runtime. That verify script belongs to the repo; when
`build-swarm`'s loop runs the work it is the same committed script passed as
`--setup`, not a second one. Put
the allowed commands in every worker spec. Preflight before the first dispatch:
worker auth, runtime version, a non-interactive shell.

Workers start from a commit. Create an **integration branch** from the
authorized base before the first wave; each later wave starts from its tip.

Keep the graph in the existing ticket or session brief. Create a separate plan
file only if its size or reuse warrants one; the user should not have to maintain
another board. A node becoming ready is an execution decision, not a new approval.

## 3. Dispatch the ready frontier

Load the installed `ringer` skill for manifests, checks, isolation, models and
status. **At most six active subagents across this work graph**, including nested
workers; other orchestrators' load still affects machine capacity. Workers don't
spawn additional workers without an explicit allocation from that same ceiling.
Choose the actual width from ready independent nodes and available resources.
Use one worker if only one node is ready; use up to six when justified.

Select the **least costly locally proven model** that can satisfy each node's
executable contract. Sol, Opus and cheaper proven models perform ordinary
implementation, research and documentation. **Astra and Fable are review
capacity**: as workers, use them only as Ringer review workers for a named
unresolved risk or applicable review requirement, never for implementation.
Either may hold the lead seat under WORKFLOW's lead-seat rule. A failed ordinary
worker returns evidence for a bounded repair or routing decision; failure alone
does not promote implementation onto a review seat. When Joe is away, take the
worker model from WORKFLOW's standing seat preferences, fall back to the local
Ringer scoreboard, and state the choice in the report; do not stop to ask.
Measure account capacity consumed per accepted outcome, not the number of
agents launched.

Ringer's base manifest has `max_parallel`, not dependency fields. The orchestrator
dispatches **only ready nodes** in each run, then validates/integrates results and
recomputes the frontier. **One wave per Ringer run**: join it before the next
dispatch, and never start a second run under a name that is still live. Keep
one job/run name across stages. Do not invent
`depends_on` fields or start blocked workers that sleep waiting for other files.
For existing local tickets with committed checks, the canonical `build-swarm`
loop is an available executor of the same plan: its preparation and safety screen
remain required, and an explicit screened `--wave` can be up to six. Its native
default is still one; its accepted run budget may limit it further. The six-worker
ceiling does not enlarge a runtime's task budget. No new tickets solely to use
that executor.

Each worker packet contains the bounded assignment, input artifact/revision,
owned files, prerequisite results, authorization limits, runnable check and
expected patch/report. Use isolated worktrees for concurrent code writers;
export their results for integration. Workers keep raw transcripts outside the
orchestrator and return a short result: changed paths, evidence, assumptions,
blockers and the artifact to integrate. Workers don't push shared branches,
deploy, edit shared trackers or open interactive sessions for Joe.

Review packets are smaller than build packets: include the accepted intent,
exact diff or revision, relevant verification evidence and the specific question.
Exclude conversational history and unrelated repository surfaces. The reviewer
returns findings and evidence; the ordinary orchestrator owns disposition,
fixes and integration.

Check current resource pressure before fan-out: memory (`memory_pressure` on
macOS when available) and **CPU load** (`uptime`), plus existing owned servers
and heavy jobs. High or unknown pressure means start smaller, not six by
default. Keep worker checks scoped and light: a worker runs its acceptance
tests and focused tests, not the whole suite. Run the full suite, builds and
other heavy integration checks centrally, once per wave, one at a time and
throttled when the machine is loaded, after the relevant branches join. If a worker genuinely requires a heavy
check, schedule that node exclusively. On OOM or quota failure, preserve results,
reduce load and diagnose before retrying; no mass restart of the same workload.

## 4. Join, verify and continue

Check delivered artifacts against ownership and scope before applying them.
Integrate in dependency order, resolve overlaps centrally, then run checks that
exercise the combined outcome. A worker's green test doesn't prove integration.
Commit each verified chunk to the **integration branch**, one commit per ticket.
The base branch stays untouched until Joe merges or replays it; do not leave a
wave's work uncommitted while the next wave starts. The orchestrator
**regenerates generated artifacts** in the real checkout; a worker's generated
copies are evidence only. Before reporting any state, name the checkout and the
backend it was read from.
If checks fail, assign a bounded repair under the same ticket; don't manufacture
a new ticket for each failure. Use focused review only for a concrete unresolved
risk or existing requirement. Additional rounds need new evidence or a material
change; routine successful work doesn't automatically trigger a panel.

Keep one place for human questions: record the real dependency on the parent
ticket (`Waiting on:` plus `Status: needs-human`) and present it through this
orchestrator. Preserve ready independent branches of the same outcome in the
working graph; a parked ticket must not be redispatched by an unattended loop.
Continue other authorized work while questions wait. Stop when no safe ready
work remains, with one consolidated question report. A `needs-human` ticket is
**closed only by Joe**; the orchestrator may recommend closing it in the report.
An unanswered decision is **never silently dropped**: park it on its ticket,
keep working what doesn't depend on it, and put it at the top of the report.

End the run with one report in a fixed shape: **shipped** (by chunk, with its
commit), **what each check proved**, **not verified**, **waiting on Joe**. List
tickets Joe asked for apart from tickets the orchestrator filed itself. Add seat
usage: the orchestrator's context at the start and end of the run, and the
workers' totals from Ringer's summary.

When the outcome passes, close its ticket with evidence and essential decisions.
Use `ship-acceptance` when actually delivering the parent intent; its accepted
evidence requirements remain binding. Update the bound session record and leave
a compact next-work handoff. Before stepping away, finish or verifiably pause
owned workers and release disposable resources through their actual controls.
