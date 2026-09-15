# Hermes TokenUsage project-manager pilot — 2026-09-15

Status: completed with an incomplete verification gate

Related concept: [Hermes project manager concept](hermes-project-manager-concept.md)

## Purpose

Test whether one persistent Hermes bot can manage a project without implementing
the work itself. The bot should resolve project state, select a bounded outcome,
delegate execution to Codex/Sol, delegate independent verification to Claude/Opus,
preserve existing work, and return an evidence-based result.

This was a direct Hermes pilot. Astra and Fable were excluded; neither was invoked.

## Configuration

- Hermes profile: `/Users/joe/.hermes/profiles/pm`
- Project: `/Users/joe/Agentic-Mini/_Tools/TokenUsage`
- Hermes model: `gpt-5.6-sol-900k` through `openai-codex`, medium reasoning
- Project branch and revision: `codex/local-dashboard` at
  `c2495fd20a2e9ac62781b83d6d65769bc9fce6a1`
- Manager session: `20260915_100413_92afe5`
- Codex worker: `gpt-5.6-sol`
- Claude verifier requested: `claude-opus-5`

The profile's `SOUL.md` now makes Hermes a manager only. It may inspect the repo and
maintain `_pm/` records. It must delegate source, test, product-documentation,
build, and configuration changes to Claude Code or Codex. It may not take over a
failed worker's implementation.

The initial and recovery prompts are retained in the profile under `pilots/`.

## Project state found

Hermes found no authorized implementation frontier:

- the planning tracker was resolved and its checker reported `Frontier: none`;
- build tickets 01–03 and 06 were done;
- tickets 04, 05, 07, 08, and 09 were `needs-human`;
- overall A1–A4 acceptance remained pending;
- the only worktree change was the pre-existing untracked
  `_pm/sessions/2026-09-15-joe.md`.

The bot therefore used the pilot's no-change fallback. It asked Codex/Sol to verify
the empty frontier and propose one future improvement, rather than inventing or
entering held product scope.

## Delegation result

### Codex/Sol

The successful Codex worker ran read-only in the foreground without a PTY.

- Codex thread: `01a0a56a-8114-7701-a453-2fe6c5ce86c3`
- Result: `no-ready-outcome`
- Proposal: add a Python 3.11+ preflight to `checks/suite.sh` and document the
  supported invocation in `README.md`
- Reason: the suite currently selects the first `python3` on `PATH`. Apple Python
  3.9 fails incidentally at `sqlite3.Connection.setlimit`; Homebrew Python 3.14
  passes the supported-runtime suite.
- Status: proposal only; it was neither authorized nor implemented.

The worker reported no edits, staging, commits, pushes, or additional agents.

### Claude/Opus

The Claude verifier did not reach model inference.

- Claude Code version: 2.1.270
- Requested model: `claude-opus-5`
- Invocation/session ID: `9041fa46-5f3c-43a3-89a2-07eeddf69a11`
- Error: OAuth session expired and could not be refreshed
- Claude usage: zero model tokens

Hermes attempted `claude auth login`. The browser login process was stopped because
an unattended project manager must not initiate interactive account authorization.
The profile now requires an auth preflight and explicitly forbids unattended login
flows.

## Verification evidence

Hermes ran the main suite with the supported Homebrew Python path:

```sh
PATH="/opt/homebrew/bin:$PATH" bash checks/suite.sh
```

Observed result: exit 0; documentation/accounting, pricing, and attribution checks
passed; the test batches passed with 9 usage, 1 fragment, 3 partition, 8 pricing,
8 review, 9 consensus, and 96 package tests; Vite built 17 modules in 106 ms.

Final repository state:

- branch and HEAD unchanged;
- no tracked or staged diff;
- only `_pm/sessions/2026-09-15-joe.md` remained untracked;
- that file's SHA-256 remained
  `52ee25b841475bcc245cfb0b83165b26eeb7266694fd30202d273e66b76c6059`;
- nothing was committed, pushed, or deployed.

The manager/implementation boundary held. The complete process gate did not pass
because independent Claude/Opus verification was unavailable.

## Runtime failures and recovery

1. The initial suite used Apple Python 3.9 and failed at an API documented only for
   the supported Python 3.11+ runtime. Hermes corrected the path and reran the
   suite successfully.
2. The first Codex command used a PTY. Oh My Zsh intercepted it with an update
   prompt before the worker started.
3. A second background PTY attempt let Codex exit but left Hermes waiting on the
   persistent shell through `process_manage(wait)`. The shell and first manager
   invocation required external interruption.
4. The same Hermes session was resumed with a recovery prompt. A foreground,
   non-PTY Codex run completed normally.
5. Claude authentication had expired. The independent verification gate remained
   incomplete.

This cycle required two kinds of human intervention: process recovery and stopping
an inappropriate interactive authentication attempt. It does not yet demonstrate
unattended reliability.

## Consumption evidence

The counts below are observed runtime records. They describe tool/model activity;
they do not by themselves establish how the account converts each category into
credits.

| Surface | Calls | Input | Cached input/read | Output | Reasoning |
|---|---:|---:|---:|---:|---:|
| Hermes manager session, cumulative | 22 | 92,181 | 1,421,824 | 10,345 | 3,260 |
| Recovery invocation only | 10 | 21,454 | 798,336 | 5,780 | 2,103 |
| Successful Codex/Sol worker | one session | 787,464 | 680,960 included in input | 10,700 | 5,563 |
| Claude/Opus verifier | failed before inference | 0 | 0 | 0 | 0 |

The Codex worker's task was too broad for the value produced: it inspected most of
the repo and accumulated a very large context to confirm an empty frontier. Model
routing alone does not solve account consumption. The manager must also minimize
ambient plugins/tools, read the tracker before running broad checks, name relevant
files, and cap the evidence needed for each worker.

## Changes made after the pilot

The Hermes profile now requires:

- tracker-first frontier resolution;
- no broad build or repository scan merely to confirm there is no ready work;
- foreground noninteractive CLI workers without PTYs;
- auth and model-availability preflight before declaring a worker gate;
- no interactive login or credential flow during unattended operation;
- narrow worker file/check scope and omitted unused plugins, apps, MCP servers,
  slash commands, and multi-agent capability;
- captured worker session IDs, exits, reports, and usage.

PM 0.20 was separately released before the pilot. It makes Sol and Opus the ordinary
session tier and reserves Astra/Fable for bounded Ringer reviews. This pilot adds a
second constraint for future PM work: context and tool surface need budgets as much
as model seats do.

## Verdict and next test

The role boundary is viable: Hermes behaved as a manager, respected held scope,
delegated to Codex, preserved existing work, and did not code. Operational autonomy
is not yet proven because PTY handling required recovery and Claude authentication
blocked the independent gate.

A second pilot should start only after Claude Code authentication is restored and a
single small outcome is explicitly authorized. It should use a narrow Codex or
Claude implementation brief, the other ordinary model as independent verifier,
foreground non-PTY invocation, a preflighted environment, and a recorded context
budget. Success means no process intervention, both worker reports captured, the
change verified, and materially lower context use per accepted outcome.
