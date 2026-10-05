# PM Dev vs a software factory

> Written 2026-10-05 from Joe's landscape notes (`software-factory-notes.md`), the pm plugin source (`_Core/_Plugins/dc-dev-plugins/pm`, v0.23.0), and the DataCraft Software Factory site (`_Core/_Plugins/datacraft-factory-site`, dated 2026-09-15). The Hermes trial status is as of that site; it may have moved since.

## The one-line answer

A software factory is a system where **triggers, not humans, start agent sessions** (Matt Pocock's definition). PM Dev already has almost every other layer of a factory. What it's missing is the trigger layer and a lookahead on decisions. Today every session starts because Joe opened it and ran `whats-next`, and a decision only gets prepared once an agent has run into it.

## What a factory is, in short

The lifecycle splits three ways (Iusztin): **planning** is human-driven (intake, spec, tickets), **execution** is agent-driven (implement, review, CI), and **improvement** is a feedback loop (every human correction becomes an automated check). Humans keep three touchpoints: writing and labelling the work, approving plans, and reviewing one-way-door changes before merge. Everything else is AFK.

On Dan Shapiro's five levels, PM Dev sits at **level 4** (developer acts as PM: writes specs, reviews outcomes), with orchestrate, session-succession and Hermes as experiments toward a level-4.5 "factory with gates." Level 5 (dark factory) isn't the goal; every serious source (Horthy, Roelants, Iusztin) says to keep planning and architecture human.

## Layer by layer

| Factory layer | PM Dev today | Gap |
|---|---|---|
| Intake / backlog | `discovery`, `docs/intent/inbox.md`, `/to-tickets`, outcome-sized tickets in `.scratch/` | None worth fixing. This is stronger than most factories. |
| **Triggers** | **Joe.** `whats-next` opens every session; `stepping-away` *offers* the next one. Hermes (trial) is the first attempt at a watcher. | **The main gap.** Nothing starts work without Joe, except an `orchestrate` run he launched. |
| Isolation | Worktrees per sibling session, integration branch for orchestrated runs, credential-guard hook | Fine for now. Sandcastle/Docker would add filesystem and network isolation (see `03-sandcastle.md`). |
| Orchestration | `orchestrate` (up to 6 Ringer workers), `build-swarm` waves, `sibling-sessions`, `session-succession` beta | Rich, but the manager is an LLM session whose context is the biggest cost (pm-021: 2.6x usage when it was the default). |
| Quality gates | `verify-before-done`, conditional `cross-review-gate`, Astra/Fable review seats, `ship-acceptance` | Good. Matches Matt's ladder: checks, then agent review, then human. |
| **Human-question queue** | `Waiting on:` + `Status: needs-human`, presented together | **Second gap.** It's reactive: a ticket joins the queue only when an agent hits the question, and nothing prepares the answer ahead of time. |
| Learning loop | `stepping-away` routes durable lessons; Compound Engineering's counterfactual test | Not measured. A factory tracks the human-correction rate and expects it to trend down. |
| Observability | Ringer receipts, token records per orchestrated run, `board.html` | Fine for an experiment. |

## Where the bottleneck really comes from

Joe's description: he has to get involved with every task, even the ones that don't need judgment. Reading the pm source, that's by design rather than a bug:

- The **default loop is one session, one outcome, Joe in the loop**. Orchestration is opt-in and was pulled back from being the default because of cost.
- Judgment isn't declared up front. The agent discovers mid-session that it needs Joe, so Joe has to be present in case that happens.
- When a judgment item does surface, it shows up as a bare question (`Waiting on: who, what, since when`) rather than a packet with options, a recommendation and the plan for "go."

So the fix isn't another orchestrator. It's three smaller changes:

1. **Declare the gate at planning time.** When `/to-tickets` writes tickets, mark the few that need Joe (`Gate: human`): plan approvals, taste, one-way doors, client-facing calls. Everything else is AFK by default.
2. **Let a dumb loop start the AFK tickets.** A script picks the next ready, unblocked, ungated ticket, runs a headless agent in a worktree, runs the checks, and merges to an integration branch. No LLM manager, so management costs nothing.
3. **Prep decisions ahead.** As soon as a gated ticket is headed for the frontier (its blockers are all AFK work), a read-only agent writes a decision packet and parks it as `needs-human`. Joe says `go` and the loop picks it up on the next tick.

`02-judgment-lookahead.md` has the design; `experiments/01-runway/` is a working version.

## How this relates to Hermes

Hermes is the same idea with an LLM as the manager: it watches the tracker, selects work, delegates through PM and Ringer, recovers failures, and escalates at judgment points. Runway is the deterministic counterpart, the Sandcastle-style "explicit pipeline you can read." They answer the same question two ways, which makes them a good A/B:

- **Runway (script manager):** zero management tokens, predictable, but can't diagnose a failure; it parks it for Joe.
- **Hermes (LLM manager):** can diagnose and retry intelligently, but every cycle costs context and its behaviour is harder to audit.

A likely end state is a hybrid: the script does selection, sequencing and the lookahead, and only calls an LLM (Hermes or a bounded Ringer task) when something fails. **Open question for Joe:** what did the Hermes trial on TokenUsage show? If it already proved recovery works, Runway's failure path can hand off to it instead of parking.

## Lessons that apply directly

- **Automate the single worst bottleneck first** (Iusztin). Here that's "Joe starts every ticket," not parallelism.
- **Loops are only as safe as their verifiability** (Horthy). Runway only auto-merges to an integration branch when the project's check command passes, and the base branch only moves when Joe merges. Projects with weak checks aren't good first targets.
- **Plan carefully, execute cheaply.** The gate is set during planning, when Joe is already thinking about the work.
- **Measure attention, not throughput.** PM's own success metric ("accepted outcomes per hour of Joe's attention") is the right one. For Runway that's touches per ticket and time from "packet ready" to "go."
