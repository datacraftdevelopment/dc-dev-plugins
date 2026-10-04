# PM plugin evolution — what changed, and did it help

One row per shipped change to `pm` (and the plugins it leans on). The *Did it
help?* column is the point of this file: every change starts **pending** and is
filled in from a real run, never from the intent that motivated it. Add the row
when the version ships; come back when the evidence exists. Detail lives in the
dated note beside this file, or the intent under `docs/intent/`.

Outcome values: `pending` (no run yet) · `helped` (evidence named) · `no change` ·
`hurt` (reverted or amended, say what happened) · `unmeasured` (ran, nobody looked).

| Date | Version | What changed | Why | Did it help? |
|---|---|---|---|---|
| 2026-09-12 | pm 0.17.0 | Local tracker by default, `docs/intent/inbox.md` for loose asks, waiting as a tracker state, optional client-face hook. `MIGRATION-0.17.md`. | TASKS.md files drifted; loose asks had no home. | **unmeasured.** Tracker and inbox are in daily use on every repo since; nobody has counted whether asks stopped getting lost. |
| 2026-09-14 | pm 0.18 → 0.19 | Shared autonomous workflow across Claude Code and Codex; lean subagent orchestration; optional succession beta. `2026-09-14-shared-workflow.md`. | One SDLC, two hosts. | **hurt, then amended.** Orchestrator lanes (pm-018) cost more in babysitting than they saved; retired by 0.21's sibling sessions. Succession stays beta, unproven. |
| 2026-09-15 | pm 0.20 | Model economy: Sol/Opus for ordinary work, Astra/Fable as Ringer review seats only. `2026-09-15-pm-model-economy.md`. | Review seats were being used as interactive sessions. | **pending.** The measure is account capacity per accepted outcome; no before/after has been recorded. |
| 2026-09-20 | pm 0.21.0 | Orchestrate on a context budget, fresh-session start, acceptance tests before dispatch, integration branch. Then, same day: orchestration made opt-in, one-session loop restored, `sibling-sessions` added. `2026-09-20-pm-orchestrated-runs.md`. | Two field runs spent more on the orchestrator re-reading itself than on workers. | **hurt as default, helped as opt-in.** The week orchestration was the default, Claude Code usage went 2.6x on doubled calls; the revert is the evidence. Sibling sessions: **helped.** In regular use since as the default way to parallelize; Joe, 2026-10-02: "surprisingly useful." It replaced the watched-lane pattern (pm-018). No usage number has been recorded against that pattern. |
| 2026-09-24 | pm 0.22.0 / 0.22.1 | `board` skill renders the tracker as one read-only HTML list; accepts bold header keys. | Reading `.scratch/` by hand was slow. | **pending.** Is the board opened more than once a session? Nobody has checked. |
| 2026-09-26 | pm 0.22.2 · ui-test 0.3.1 · fm-dc 0.8.2 | Three sentences from Helix: ui-test reference-state precondition and `comparison` BLOCKED, orchestrate skeleton-first ordering, fm-dc "the existing file is the spec". `2026-09-26-helix-wording-takes.md`. | Shopify's checkpoint-gate loop, read against PM. | **pending.** Measures are in the note: next reference comparison, next orchestrated first wave, next rebuild engagement. |

## Rules for this file

- A row is added by the commit that bumps the version. A row without a version
  is a plan, and plans go in `docs/intent/`.
- Fill *Did it help?* only from something that happened: a run, a usage number,
  a revert, a session where the change was or wasn't used. "It should help" is
  not an entry.
- `unmeasured` is an honest answer and better than a guess. It also marks the
  changes worth measuring next.
- When a change is reverted or amended, the row stays and says so. The history
  of what didn't work is half the value.
