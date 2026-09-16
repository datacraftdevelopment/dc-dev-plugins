# Hermes TokenUsage project-manager pilot 2 — 2026-09-15

Status: completed. The product work was verified, but nothing was committed, and two
boundary issues are open.

Related: [pilot 1](hermes-tokenusage-pilot-2026-09-15.md) ·
[Hermes project manager concept](hermes-project-manager-concept.md)

## Source of this record

This run left nothing in the profile's `pilots/` folder, which still holds only
pilot 1's prompts and usage. This record was reconstructed on 2026-09-16 from the
following sources:

- the Hermes PM profile's `state.db` (sessions, messages, tool calls, and
  `session_model_usage`);
- `logs/errors.log`, `logs/gui.log`, and `logs/process-results/`;
- the TokenUsage working tree and its tracker in `.scratch/tokenusage-build/`;
- a fresh run of the TokenUsage suite by Claude Code (see Verification).

## Configuration

- Hermes profile: `~/.hermes/profiles/pm` (pilot 1's manager-only `SOUL.md`, which
  Joe updated at 11:28)
- Surface: Hermes desktop, canonical Bot Chat session `20260915_095553_cdbd7e`,
  09:55–21:20
- Manager model: `gpt-5.6-sol-900k` via `openai-codex` (subscription)
- Project: `~/Agentic-Mini/_Tools/TokenUsage`, branch `codex/local-dashboard`,
  base `c2495fd`
- Delegation: **all worker calls went through Ringer** (`ringer.py run … --identity
  pm`), run as Hermes background processes whose completion notifications woke
  the Bot Chat. Pilot 1, by contrast, called Codex directly.
- Workers: Codex `gpt-5.6-sol` for implementation, Astra for a review panel, and
  Claude `claude-opus-5` for acceptance once Fable's usage ran out.

## What Joe asked for

At 11:28 Joe asked Hermes to be the project manager for TokenUsage and keep it
going. Joe then pointed it at the dc-dev-plugins PM skills and told it to move
from one ticket to the next, running several at once where possible, and to bring
Joe in only when needed. At 14:53 Joe told it that Fable was used up and to use
Opus for Claude work.

## What happened

| Time | Event |
|---|---|
| 11:30 | Joe answered a scoping question on held findings H1–H3 (a `clarify` prompt) |
| 11:49 | Ticket 09 (H1–H9) dispatched to a Ringer recovery worker. An earlier direct-Codex draft was quarantined and not used as evidence |
| 11:58–12:57 | Ticket 09 cycle: recovery → Astra review (exit 1, eight reproduced findings triaged) → repair → check-repair (exit 1, sandbox loopback bind denied) → follow-up → final repair |
| 12:11 | Fable acceptance was blocked by its usage limit, so ticket 09 stayed open for independent acceptance |
| 13:05–14:31 | Ticket 10 (bounded live-source refresh), which Hermes filed itself: diagnosis → implementation (2 attempts, 462K tokens) → tracker repair (2 attempts, 192K tokens). Host suite 129/129 |
| 14:51 | Joe asked Hermes to install the Twilio SMS skill. It was installed and dry-run; no SMS was sent |
| 14:55 | Status reported as 5 of 10 tickets done |
| 15:07 | Ticket 09 accepted by Claude Opus 5 through Ringer. Nonblocking findings were filed as ticket 11 (dispatched) and ticket 12 (pruning, parked as destructive) |
| 15:52 | Joe authorized ticket 05 (SQLite fixture warnings) through a `clarify` prompt |
| 15:54 | Tickets 05 and 13 ran **in parallel** |
| 16:03–16:21 | Ticket 13 (retained-state growth measurement) finished. Ticket 05 needed three runs: the first two exited 1 (the validator left an untracked log file, then a sandbox loopback exclusion) and the third passed |
| 16:29 | Ticket 14 (pricing fixture cleanup) passed. The suite was 134/134 |
| 17:32 | Hermes asked whether to commit. **The prompt timed out with no answer**, so nothing was committed |
| 17:33 | Hermes reported all 14 tracked tickets complete |
| 17:45 | Joe started a separate YoJoe session (see below) |

Ringer notifications: 16 runs, of which 11 exited 0 and 5 exited 1. Every failed run
was handled: Hermes triaged or repaired it without Joe stepping in.

## Manager boundary: held

Hermes wrote files through `write_file` and `patch`, and every file it touched was
one of these:

- tracker files (`.scratch/tokenusage-build/map.md` and `issues/*.md`);
- `_pm/` briefs, triage notes, and the session log;
- Ringer manifests and check scripts under `~/.ringer/work/`;
- runtime config for the local dashboard under `~/.local/share/tokenusage/`.

Product code changed only through `git apply` of Ringer worker patches, each saved
first to `_pm/artifacts/` and checked with `git apply --check`. One patch was
reverse-applied (`-R`) and reapplied during the ticket 09 repair. Hermes wrote no
source code itself.

## Open issues

1. **Needs-human tickets closed by the manager.** Tickets 04, 07, and 08 were filed
   as needs-human, meaning "quarantined until a human approves it and writes its
   check." Hermes marked all three `done` without a `clarify` prompt or an answer
   from Joe:
   - 04 and 08 were marked "superseded by host integration evidence";
   - 07 was marked a duplicate of 05.

   The reasoning looks sound, but the tracker rule gives that decision to a human.
   By contrast, Hermes did ask before starting ticket 05.
2. **Pre-existing file modified.** Hermes patched `_pm/sessions/2026-09-15-joe.md`
   four times. That untracked file existed before the run, and pilot 1 left it
   byte-identical. Appending to a session log is probably intended, but it
   should be an explicit rule.
3. **Decision prompts time out silently.** The commit question at 17:32 expired
   with no answer, and the result is an uncommitted working tree of 19 modified
   and 25 untracked files. The one-line report said this, but Joe was not
   notified by any other channel, even though the SMS skill was already
   installed.
4. **Ticket count moved.** The status at 14:55 was "5 of 10"; the final report said
   "14 of 14." Hermes filed tickets 10–14 during the run, so the final count
   covers work the manager defined itself: 10, 11, 13, and 14 were done, and 12
   was parked.

## Verification

Hermes reported 134/134 tests, a clean build, 0 `ResourceWarning`s, and ticket 09
accepted by Opus. Claude Code independently re-ran the suite on 2026-09-16:

```sh
cd ~/Agentic-Mini/_Tools/TokenUsage
PATH="/opt/homebrew/bin:$PATH" bash checks/suite.sh
```

It exited 0. The package suite ran 134 tests, all OK. `tsc --noEmit` and the Vite
build passed (17 modules). This confirms the integrated working tree is green. It
does not re-check the loopback browser flows or the Opus acceptance content.

Repository state on 2026-09-16: HEAD still `c2495fd`, and nothing committed,
pushed, or deployed.

## YoJoe session: ended on a usage limit

Joe opened session `20260915_174015_9fd540` for a new YoJoe project. Its first reply
described **TokenUsage's** state (branch `codex/local-dashboard`, "14 tracked
outcomes") because the session had no `cwd` yet; Joe gave the YoJoe path
afterwards. At 18:26 the next turn failed after three retries with
`HTTP 429: The usage limit has been reached` on `openai-codex`. The session
has sent nothing since, and it is still listed in `runtime/active_sessions.json`.

## Log health

- `errors.log`: 965 lines, but only 3 at ERROR level: two `computer_use capture
  failed` errors (the YoJoe session-creation attempt, blocked by a pending macOS
  Accessibility/Screen Recording permission) and the 429 above.
- The warning-level noise has two sources: 92 `Copilot token exchange degraded to
  RAW token` lines, and a browser CDP supervisor retrying a dead port
  (`127.0.0.1:62369`) at least 203 times through 17:05. Neither blocked the work.
- `gui.log`: client disconnects only; no dispatch crashes or send failures.

## Consumption evidence

| Surface | Calls | Input | Cache read | Output | Reasoning |
|---|---:|---:|---:|---:|---:|
| Bot Chat manager (main) | 311 | 1,530,177 | 72,062,720 | 124,243 | 45,535 |
| Bot Chat background review | 32 | 91,745 | 7,372,416 | 16,463 | 6,665 |
| Bot Chat approvals + compression | 32 | 38,592 | 0 | 9,300 | 0 |
| YoJoe session (before 429) | 43 | 515,085 | 4,313,856 | 26,087 | 7,521 |

The Bot Chat made 374 tool calls in total. The largest groups were `terminal` (234),
`read_file` (191), `browser_exec` (68), and `search_files` (64). The manager's
cache reads of 72M tokens came from a single long-lived conversation, compacted
once at 14:25. That volume, plus the Ringer workers (the two ticket 10 runs alone
used 654K tokens), is the likely cause of the 18:26 usage-limit stop.
Worker-side usage for the other runs is in the Ringer run records and is not
totalled here.

## Verdict against pilot 1's success criteria

| Criterion | Result |
|---|---|
| No process intervention | **Met.** No PTY hangs, and no manual recovery across 16 Ringer runs |
| Both worker reports captured | **Met.** Codex worker patches and Opus acceptance were saved as `_pm/artifacts/` and Ringer runs |
| Change verified | **Met.** 134/134, re-run independently |
| Lower context per accepted outcome | **Not met.** The manager context was very large, and the account hit its limit |

Joe's summary that Hermes "powered through" holds up: it ran seven hours with
little supervision, delegated through Ringer, ran two tickets in parallel, and
recovered from five failed runs on its own. Before a longer unattended run, fix
these:

1. Needs-human tickets are closed only by Joe.
2. An unanswered decision prompt is escalated (for example by SMS) rather than
   dropped.
3. New sessions bind to their project `cwd` before they report state.
4. The manager context gets a budget, or is rotated into fresh sessions
   between tickets.
