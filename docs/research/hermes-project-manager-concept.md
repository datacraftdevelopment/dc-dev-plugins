# Hermes as a persistent project manager

Date: 2026-09-15  
Status: exploratory research and discussion; no accepted design or implementation authorization  
Audience: Joe, Hermes, Claude, and Codex

## Why we are discussing this

Joe has been experimenting with DataCraft PM, especially orchestration,
What's Next, and session records. Those pieces are working well together, but
he still has to initiate, supervise, and reconnect too much of the work. His
available time at the computer limits throughput.

The direction is toward a software factory: substantial projects keep making
progress within agreed boundaries while Joe participates where his judgment
matters. Joe intends to try Hermes later today. This document preserves the
conversation so that he can discuss the idea with Hermes and Claude.

**Joe's concept:** one persistent Hermes bot for each substantial project. Each
bot acts as that project's manager, has access to its repository and project
folder, coordinates Claude Code or Codex sessions, and brings Joe into the work
when needed. The Hermes manager does no coding.

This is deliberately loose. No skills, plugin changes, installations, automation,
new operating policy, or client-project pilot are requested by this document.
The responsibilities and trial ideas below are proposals for discussion.

## Research scope and confidence

Codex inspected current first-party Hermes documentation, the existing library
page on Hermes, the private PM source, the installed Codex PM manifest and host
instructions, and PM's recorded review evidence. Hermes was not installed or
exercised during this research. Documented capabilities are distinguished below
from proposed integration behavior. Upstream documentation is a moving target;
verify the installed Hermes version during the eventual trial.

The earlier library research is dated 2026-06-26 and still records first-hand
evaluation as pending. It supplies background, not evidence that this integration
works. Local reference: `_Core/library/wiki/craft/agents/systems/hermes.md`.

### First local setup observation — 2026-09-15

Joe installed Hermes and created a test profile at
`/Users/joe/.hermes/profiles/pm`. Read-only inspection found its default model is
`gpt-5.6-sol-900k` through the `openai-codex` provider at medium reasoning effort.
Its `SOUL.md` currently identifies it only as a persistent named PM agent, and
`terminal.cwd` is `.`. That is a useful persistent PM test bot, but it is not yet
bound to one project or given the manager/execution boundary proposed below.

The first managed TokenUsage run is recorded separately in
[Hermes TokenUsage pilot — 2026-09-15](hermes-tokenusage-pilot-2026-09-15.md).
It tested the manager-only boundary, direct Codex/Sol delegation, a blocked
Claude/Opus verification seat, recovery from PTY process tracking, and measured
context use.
No bot behavior, delegation, scheduling, or session handoff has been tested by
this observation, and the profile was not modified.

## What Hermes provides

### Persistent project identities

Bot Mode presents separate Hermes profiles as named bots. Each has its own role,
model, memory, skills, configuration, and conversation history. Bots have a
persistent canonical chat and recurring routines. This is a close conceptual
match for one enduring project manager. [H1]

Bot Mode also supports group conversations, attention indicators for human
questions, and bot-to-bot messaging. These are optional capabilities; a fleet of
project managers need not begin with group deliberation. For unattended operation,
the transport matters: cross-connection Desktop relaying depends on Desktop being
open, while registered peers support direct communication without it. [H1]

### Project access and boundaries

A profile's state directory and its working directory are separate. A profile
can have an explicit project path through `terminal.cwd`. Profiles do not sandbox
filesystem access: the default local backend has the user's filesystem access.
Standing instructions alone do not enforce a project boundary. [H2]

Consequently, "one bot per project" gives useful separation of state, but any
required restriction to that project's files must be established separately.
Having access also does not mean the bot has complete or current knowledge of
everything in the folder.

### Scheduling and continuity

Hermes routines use its cron infrastructure. Scheduled work can carry its previous
output forward with continuity enabled; monitoring can suppress unchanged output.
The docs also describe script-only checks that avoid an LLM turn. This offers
building blocks for periodic progress checks and concise updates. It does not
provide our project's scheduling policy automatically. [H3]

### Connections to coding agents

Hermes bundles CLI delegation guidance for Claude Code and Codex. Claude's guide
describes noninteractive execution, session continuation, and interactive terminal
sessions. Codex's guide describes command execution, background jobs, and process
monitoring. [H4, H5]

These demonstrate available integration approaches, not a verified bridge into
Joe's current desktop sessions. A process handle is not necessarily a resumable
conversation identity. Bringing Joe into the exact working session, returning his
answer, and resuming unattended operation remain important trial questions.

The bundled guides are source material to evaluate; their launch recipes do not
automatically preserve DataCraft's Ringer routing, PM records, or existing grants.

## What PM already provides

The private development source is PM **0.19.0**, released in commit `7979121` on
2026-09-14. The installed Codex edition inspected was
`0.19.0+codex.20260914191241`. The public derivative inspected was 0.12.0; the
private development edition is the relevant foundation for this concept.

PM 0.19 already has:

- Outcome-sized tickets and a compact graph of worker assignments.
- One execution orchestrator that prepares, delegates through Ringer, integrates,
  and verifies; up to six workers when resources and independence permit.
- `whats-next`, `checkpoint`, and `stepping-away` for session continuity.
- Decisions parked on the existing tracker with `Waiting on:` and `needs-human`.
- Evidence requirements and delivery records.
- Optional session succession with durable launch and ownership states.

See [PM's workflow](../../pm/WORKFLOW.md),
[orchestration procedure](../../pm/skills/orchestrate/SKILL.md), and
[0.19 intent](../intent/pm-019-session-succession.md).

PM's current default is manual session rotation. Automatic succession is an
opt-in beta. Its recorded tests establish helper behavior; actual host startup,
required clicks, resource release, cross-machine load, and net effort saved still
need live evidence. Earlier pilots shipped work but incurred restarts and recovery
effort, including a memory crash. See the
[release evidence](../reviews/pm-019-fable.md).

## Proposed division of responsibility

| Participant | Proposed ownership |
|---|---|
| Joe | Direction, priority tradeoffs, product judgment, and actions needing his decision |
| Hermes project manager | Continuity across sessions, next authorized outcome, progress monitoring, consolidated questions, and execution handoffs |
| Claude Code or Codex with PM | Technical planning, worker assignments, integration, verification, and execution-session records |
| Ringer workers | Bounded implementation or investigation with evidence |

The manager would hand an execution session an outcome and its relevant context.
The session would return status, evidence, unresolved decisions, and a compact
handoff. This is a proposed boundary, not a new dispatch mechanism or approved
change to PM's existing one-orchestrator rule.

The potential gain is taking over the transitions Joe currently performs. An
external manager can remain available when an execution session ends, reaches a
context boundary, or fails. Whether it can reliably reconcile that event and
continue work must be demonstrated.

## Questions that determine whether this saves Joe time

### 1. Who owns session launching?

Hermes and PM succession must not independently launch the next execution session.
One owner needs to track creation, acknowledgement, current checkout ownership,
and retirement. The existing PM succession states may be reusable, but that is
an integration hypothesis. A missing response must not cause duplicate launches.

### 2. How much choice does the manager have?

An open question from the conversation: should the bot choose the next outcome
from an agreed project backlog, or receive a bounded package whenever Joe steps
away? No answer has been accepted yet.

The useful manager could continue approved independent work while a decision
waits. Existing scope, runtime budgets, and release permissions still apply.
Merely relaying every worker question would leave Joe with much of today's work.

### 3. Where does project truth live?

The proposal is to retain accepted intents, decisions, the declared tracker, and
delivery evidence as the project record. Hermes memory helps navigation and
continuity; the bot refreshes its understanding from those records before acting.
Avoid a second backlog or an independent authoritative account inside bot memory.

Decide who writes shared records during active execution so manager and session
do not both change ownership or status. Project access should include relevant
local records: `_pm` and a `.scratch` tracker may be gitignored and absent from a
remote clone. Hosting and synchronization remain undecided.

### 4. What does bringing Joe in feel like?

Prefer one concise question with a recommendation, consequence, and current work
status. For example:

> The import flow needs a choice about duplicates. I recommend updating existing
> records. That branch is waiting; validation work is continuing.

The example is hypothetical. The actual messaging channel, notification rhythm,
and route into a working session are open. Human replies need to reach the correct
ticket and exact execution session, including when the question has become stale.

### 5. How do several projects share capacity?

Project-specific managers still share machines, memory, and account limits. Each
one independently using PM's six-worker ceiling could overload the same host.
Some shared admission and budget control may be needed; it need not become
another management bot. Retries also need bounds and a visible stop condition.

## A possible first experiment — not yet authorized

One project, one manager, a bounded set of agreed outcomes, and one execution
session at a time would expose the important seams without building a fleet.
Joe remains free to change this shape after trying Hermes.

The trial should answer whether the manager can:

1. Read the real project state and select an authorized, unclaimed outcome.
2. Start execution with the intended PM/Ringer behavior and preserve its identity.
3. Collect evidence and a usable handoff when execution finishes.
4. Park a human decision and continue independent work within the agreed scope.
5. Recover from an interrupted session without duplicate work or invented status.
6. Bring Joe into a decision or session without making him reconstruct context.

Measure completed outcomes, Joe's interruptions and minutes spent, recovery
minutes, duplicate launches, and resource use. Starting more sessions is not by
itself success. Any specific duration, budget, host, or project remains undecided.

## Discussion request for Hermes and Claude

Please treat this as an early concept discussion. No implementation is requested.

- Is this coherent enough for a useful review now? What kind of review would help?
- Which assumptions are most likely to fail in actual Hermes operation?
- Does the proposed manager/execution boundary remove work from Joe, or duplicate
  orchestration PM already handles?
- What is the smallest observation Joe could make during his first Hermes trial
  that would strengthen or disprove the concept?
- What should remain deliberately undecided until that trial?

Codex's initial judgment: a short feasibility discussion is useful now. A formal
architecture or implementation review would be premature. The highest-value
evidence is a real session lifecycle and human handoff with the intended host.

## Light Claude second opinion

On 2026-09-15, Codex passed this note to the configured Claude Fable seat through
Ringer for a bounded discussion, asking whether a review was worthwhile at this
stage. This was one perspective, not a formal cross-review gate. The
[original report](../reviews/hermes-project-manager-concept-claude.md) is preserved
separately. Run: `hermes-pm-concept-discussion-20260915T110303Z-p72391`.

Claude agreed that a feasibility discussion is useful now and formal architecture
review is premature. Its central challenge: PM already chooses ready work and
handles blockers, so Hermes must demonstrate that it removes session transitions
from Joe rather than duplicating execution management. Its proposed first
observation is one manually configured bot completing a session lifecycle, with
a human question routed back to the right work, measuring Joe's attention cost.

Codex agrees with that emphasis, with one qualification to the report's wording:
PM's succession beta already attempts to initiate successors. Hermes's potential
advantage is an independently persistent owner that can observe and recover across
execution-session failure, not an exclusive ability to launch sessions. Neither
approach's reliability is established by this discussion.

The report passed its delivery-contract check on the first attempt. That check
verified requested sections, a source reference, and bounded length; the opinions
remain judgments and no Hermes integration was tested. The next useful discussion
can build on Joe's actual first-run observations.

## Sources

External sources were read on 2026-09-15; capabilities have not been tested here.

- **H1:** [Hermes Bot Mode](https://hermes-agent.nousresearch.com/docs/user-guide/bot-mode)
- **H2:** [Profiles and workspace boundaries](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
- **H3:** [Scheduled tasks](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)
- **H4:** [Hermes Claude Code delegation guide](https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-claude-code)
- **H5:** [Hermes Codex delegation guide](https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-codex)

Repository sources are linked beside the corresponding claims above. The June
library page is background; current Hermes claims are attributed to H1–H5.
