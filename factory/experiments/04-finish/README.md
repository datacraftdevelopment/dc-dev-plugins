# 04 · Finish step and retro (Matt's Skills v1.3 ideas in Runway)

**Question:** if Runway ends each build with a review pass and a PR body Joe can read in a minute, and logs every agent call so `/retro` can learn from the runs that struggled, does merging get faster and do retries and parks go down over time?

Background: `../../research/06-skills-v1-3.md`. Matt's `/implement-spec`, `/pr` and `/retro` cover the back half of the same flow Runway runs. Runway stays the engine (triggers, gates, lookahead); this experiment borrows the parts it was missing. All the code is in `../01-runway/runway.py`.

## What changed in Runway

1. **Test-first runs.** The run prompt tells the agent to use `/tdd` if it's installed, or to write a failing test before the code.
2. **Every agent call is logged** to `_pm/runway-runs.jsonl`: ticket, kind (prep, run, review, fix, pr), attempt, worktree, exit code, seconds, and, when the command uses Claude Code's `--output-format json`, the session id, turns, cost and token usage. Each ticket's outcome (done or parked, and how many attempts) is logged too. The defaults and both practice templates now pass `--output-format json`.
3. **Finish step.** When `loop` goes idle and every Runway ticket is done, it runs once per integration-branch head:
   - a **review** of `git diff <base>...runway/integration` against the tickets (and `spec`, if set), using `/code-review` if it's installed;
   - **one fix pass** for the findings, committed to the integration branch only if `check_cmd` still passes (otherwise it's discarded and the findings stand);
   - `check_cmd` on the final branch, as **evidence**;
   - a **PR body** in `/pr`'s shape (Summary as a picture, Evidence, Merge danger), written to `_pm/runway-pr.md`, with the review and ticket list folded underneath.
   - With `"pr": "draft"`, Runway also pushes `runway/integration` to `origin` and opens a draft PR with `gh` (or updates the body of the one already open). It never merges.
   - Then a notification: "Ready for review: N tickets, check passes, PR: …".
4. **`runway finish`** runs the same step now, whatever the queue looks like.
5. **`runway retro`** prints token use, cost and agent time per ticket, and writes `_pm/runway-retro-prompt.md`: a `/retro` prompt listing the transcripts of the runs that struggled (retries, parks, fix passes, failed calls), or the latest runs if nothing did. Start it with `claude "$(cat _pm/runway-retro-prompt.md)"` from the repo. `/retro` only proposes changes, so Joe picks what lands.

## Config

All optional, in the target repo's `runway.json`:

| Key | Default | Meaning |
|---|---|---|
| `finish` | `all_done` | `all_done`: finish when every Runway ticket is done. `idle`: whenever the queue stops, even with decisions waiting. `off`: only `runway finish`. |
| `pr` | `file` | `file`: PR body in `_pm/runway-pr.md`. `draft`: also push and open or update a draft PR with `gh`. |
| `spec` | empty | A path, URL or Linear issue for the review to read. |
| `review_cmd` | `claude -p --output-format json` with read-only tools plus `Skill` | Review agent. Also writes the PR body unless `pr_cmd` is set. |
| `fix_cmd` | `agent_cmd` | Agent for the one fix pass. |
| `pr_cmd` | `review_cmd` | PR-body agent. |

`pr` defaults to `file` because pushing to a client's GitHub is an outside action; turn on `draft` per repo.

## Run the offline test

```bash
bash experiments/04-finish/test/test_finish.sh
```

It builds a throwaway repo with three tickets (one gated, one that fails its first attempt), a local bare `origin`, and fake `claude` and `gh` commands. It checks that finish waits for the gated ticket, the fix pass lands on the integration branch, the PR body has Merge danger, a draft PR is opened once and then updated, a second `loop` doesn't re-run finish, and `runway retro` flags the retried ticket and finds its transcript. The 01 demo and the 03 Linear test set `"finish": "off"` and still pass unchanged.

## Results

- **2026-10-06, offline (fake agent, fake gh), cloud container:** all checks pass. 01 demo and 03 Linear test unchanged.

## Open questions (unverified)

- Whether `/code-review` and `/pr` load in a headless `claude -p` call when `Skill` is in `--allowedTools`. If they don't, the prompts still carry the instructions, so the output shape holds.
- Where `claude -p` keeps transcripts for runs in worktrees that were deleted afterwards. `runway retro` searches `~/.claude/projects/*/<session id>.jsonl`, which is where interactive sessions go.
- With `all_done`, a ticket blocked by a Wayfinder decision keeps finish waiting forever. Use `"finish": "idle"` or `runway finish` on those projects.
- How much the review and fix pass add per build in tokens. The new log answers that on the first real run.
