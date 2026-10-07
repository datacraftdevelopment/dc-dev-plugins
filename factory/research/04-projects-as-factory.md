# Are Claude Code Projects already a software factory?

> Written 2026-10-05 from inside a Projects thread, so it's based on the tools this setup actually exposes rather than on marketing. Projects is in beta (since 2026-09-17) and will change. Cost per thread hasn't been measured.

## Short answer

Mostly, yes. A Project with a coordinator and threads has the same shape as a factory, and it already covers the trigger, orchestration and surfacing layers that PM Dev is missing. What it doesn't do on its own is **work a ticket queue**. The coordinator reacts to messages; it doesn't read `.scratch`, notice that ticket 02 is now unblocked, start it, and prep ticket 03's decision ahead of time. That queue logic, which is Runway's whole job, is exactly the part behind Joe's bottleneck.

## Layer by layer

| Factory layer | What Projects gives today | Gap |
|---|---|---|
| Triggers | Routines (cron, GitHub webhooks, API) can start sessions; PR events (CI red, review comments, merge conflicts) wake the owning thread on their own. | Nothing fires on "a ticket became ready" or "Joe said go" unless a routine polls for it. |
| Orchestration | The coordinator splits asks into threads, each its own session with its own branch, plus shared memory and a shared files folder. | It dispatches what someone asks for. It doesn't compute a dependency frontier or sequence tickets. |
| Isolation | Each thread is a cloud container on its own branch. Device work goes through folder access or Remote Control. | Your real toolchain (Ringer, Codex lanes, local checkouts) lives on the Mac mini, so cloud threads only reach it through Remote Control. |
| Quality gates | Threads drive their own PRs to green: fix CI, address review, re-request review. Merging stays human. | Fine. Equivalent to Matt's first two brakes, with you as the third. |
| **Judgment surfacing** | `ask_decision` cards: one question, 2–4 options, one recommended. Work continues on the recommended option unless the step is irreversible. | **Reactive.** A card appears only when a thread reaches the fork. Nothing preps the next gated item while the current one runs. |
| Observability | Status checklists per thread, a project timeline, a PR list. | No tokens or cost per thread, and no "touches per ticket" metric. |
| Learning loop | Shared memory that every session reads. | Manual. Nothing turns a correction into a check automatically. |

## What a dedicated factory (Sandcastle, Runway) adds over Projects

- **Deterministic selection.** A script decides what runs next from the tracker, so the decision costs no tokens and can be audited. A coordinator decides with an LLM, which costs context on every message (the pm-021 concern again).
- **Local-first execution.** Sandcastle and Runway run on your hardware, against your checkouts and tools, with whatever model or CLI you choose. Projects is Claude-only and cloud-first.
- **Planned gates.** `Gate: human` is set while you're planning, so the loop knows ahead of time which tickets will need you and can prepare them early.

## What Projects adds over a script

- **A real UI for the human side.** Threads, decision cards and a phone-friendly timeline are a better place to say "go" than `runway go 03` in a terminal.
- **PR driving and recovery.** A thread can diagnose a red CI run and push a fix. Runway just parks the failure for you.
- **Routines.** These are the scheduler that Sandcastle and Runway both lack.

## Recommendation

Don't pick one. Use Projects as the factory floor and UI, and put the queue logic in a script:

1. Keep Runway's tracker logic (frontier, gates, lookahead) as the source of truth.
2. **Experiment 03 (revised):** a routine runs `runway tick` on a schedule (on the Mac mini via Remote Control, or against a repo the cloud can reach). Each ready AFK ticket gets its own thread to implement and drive the PR. Each gated ticket gets its packet posted as a decision card, and tapping "go" flips it to `Gate: approved`.
3. Compare that against plain Runway (experiment 01) and Hermes on the same metric: accepted outcomes per hour of your attention.

**(unverified)** Whether a routine can start a thread and post a decision card in this project without the coordinator in the middle, and what a thread costs in tokens. Both are worth checking before building experiment 03.
