---
name: orchestrate
description: "Execute an outcome through bounded subagents: prepare shared scaffolding, dispatch ready nodes of a dependency graph (up to six active workers), then integrate and verify. Use for authorized implementation or independent ticket work; worker assignments stay under the outcome ticket."
---

# Orchestrate

One session owns the outcome, integration and Joe's questions. Workers do bounded
autonomous work through Ringer. Manual session rotation is normal; succession is
a separate opt-in experiment. Read [WORKFLOW.md](../../WORKFLOW.md) for scope and conditional stages.

## 1. Frame the outcome

Read the user's request, accepted intent and existing ticket(s). Use their current
authorization. A useful outcome is the ticket; scaffolding, files, tests, reviews
and worker assignments are steps inside it. Create additional tickets only for
separately useful outcomes, independent ownership or durable unresolved work.
Do not run `/to-tickets` merely to feed a worker engine. A small direct request
may be completed without a new ticket or delegation overhead.

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

Ringer's base manifest has `max_parallel`, not dependency fields. The orchestrator
dispatches **only ready nodes** in each run, then validates/integrates results and
recomputes the frontier. Keep one job/run name across stages. Do not invent
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

Check current resource pressure before fan-out. On macOS use `memory_pressure`
when available; inspect existing owned servers and heavy jobs. High or unknown
pressure means start smaller, not six by default. Keep worker checks scoped and
light. Run full builds and other heavy integration checks centrally, one at a
time, after the relevant branches join. If a worker genuinely requires a heavy
check, schedule that node exclusively. On OOM or quota failure, preserve results,
reduce load and diagnose before retrying; no mass restart of the same workload.

## 4. Join, verify and continue

Check delivered artifacts against ownership and scope before applying them.
Integrate in dependency order, resolve overlaps centrally, then run checks that
exercise the combined outcome. A worker's green test doesn't prove integration.
If checks fail, assign a bounded repair under the same ticket; don't manufacture
a new ticket for each failure. Use focused review only for a concrete unresolved
risk or existing requirement. Additional rounds need new evidence or a material
change; routine successful work doesn't automatically trigger a panel.

Keep one place for human questions: record the real dependency on the parent
ticket (`Waiting on:` plus `Status: needs-human`) and present it through this
orchestrator. Preserve ready independent branches of the same outcome in the
working graph; a parked ticket must not be redispatched by an unattended loop.
Continue other authorized work while questions wait. Stop when no safe ready
work remains, with one consolidated question report.

When the outcome passes, close its ticket with evidence and essential decisions.
Use `ship-acceptance` when actually delivering the parent intent; its accepted
evidence requirements remain binding. Update the bound session record and leave
a compact next-work handoff. Before stepping away, finish or verifiably pause
owned workers and release disposable resources through their actual controls.
