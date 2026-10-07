# Matt's Skills v1.3 against the factory

> Written 2026-10-06 from the v1.3 changelog and the three skill pages on aihero.dev, plus this repo (`decisions.md`, research 01/04/05, experiments 01 and 03) and the pm plugin source (v0.23.0). I read the skill pages, not the SKILL.md files themselves, so details marked **(unverified)** need a look at the installed skill. Nothing was installed or updated. What was built from it is in `experiments/04-finish/`.

## Short answer

Keep Runway. Don't adopt `/implement-spec` as the factory's engine, but borrow its review step and two of its habits. Adopt `/pr` for the one merge Joe still does by hand, and use `/retro` as the factory's learning loop. Before running `npx skills update`, fix the pm plugin's two references to `CONTEXT.md`, which v1.3 renames.

## /implement-spec vs Runway

They share most of their mechanics: both read tickets as a blocking graph, run each ready ticket in its own worktree, merge into one integration branch, and close tickets in the tracker. The difference is who starts the work and who manages it.

| | `/implement-spec` | Runway |
|---|---|---|
| Starts when | Joe types it in a live session (manual only) | launchd every 10 min, no session open |
| Manager | An LLM orchestrator session | A Python script (no management tokens) |
| Parallelism | Every frontier ticket at once, as subagents | One ticket at a time (on purpose, v1) |
| Human gates | None described | `ready-for-human`, decision packets ahead of time, `go` in Linear |
| Per-ticket build | `/tdd`, red-green | Free-form prompt, then `check_cmd` |
| Merge | Rebase onto integration first, fast-forward only | `--no-ff` merge; a conflict parks the ticket |
| After all tickets | `/code-review` over the whole branch against the spec, one fix subagent | Nothing; Joe merges |
| Failure | Not described beyond the fix pass | One retry with the log, then `needs-human` |

**Why not adopt it.** Joe's bottleneck is that he has to start and touch every ticket. `/implement-spec` still needs him to open a session and run it, which is the gap Runway closes, and it uses an LLM manager, which `decisions.md` ruled out as the default (pm-021 measured 2.6x usage). It also has no gate concept that I could find. **(unverified)** whether it skips `ready-for-human` tickets. If it doesn't, running it on a Linear project would build a gated ticket without Joe's `go`.

**Why not wrap it.** Runway works one ticket per agent call, while `/implement-spec` wants a whole spec, so it can't sit behind Runway's `agent_cmd`. Running it as the whole of Runway's job would trade away the gates and lookahead.

**A real conflict.** Both close tickets in the same tracker. If Joe runs `/implement-spec` on a Linear project that Runway's launchd job is also watching, both will pick up the same `ready-for-agent` tickets. Pause the schedule first (`schedule.sh uninstall <repo>`), or keep the two on separate projects. It's fine as an at-the-desk tool when Joe is around and wants a spec built fast in one go.

**What to borrow into Runway:**

1. **A final review pass.** When the queue is empty (everything Done, or only decisions waiting), run one `claude -p` over `runway/integration` that calls `/code-review` against the spec, with one fix pass. Matt's page says this only makes sense once every ticket has landed, which matches Runway's "finish" moment. This is the biggest gap it shows: today Runway's only check is `check_cmd`.
2. **TDD in the run prompt.** Tell the agent to use `/tdd` (red-green, one slice at a time). It's a one-line change to `RUN_PROMPT`.
3. **Bring integration in before merging.** Have the agent (or Runway) merge the latest `runway/integration` into the ticket branch and re-run `check_cmd` before the merge. This matters once Runway runs tickets in parallel; at one ticket at a time it changes little.

Two warnings from his page also apply to Runway as written: tests that read gitignored fixtures, local databases or credentials can silently skip inside a worktree, and blocking edges written from ticket text are only a guess at which files tickets touch, so parallel tickets can still collide. Keep both in mind before turning on parallelism.

## /pr

It only writes the PR body (Summary as a picture, Evidence before and after, Merge Danger as one-way or two-way door plus blast radius); it doesn't open the PR. It fits the one manual step left in Runway's flow: Joe merging `runway/integration` into `main` with nothing to read but the branch.

**Change:** at the same "queue empty" moment, after the review pass, have Runway open a draft PR from `runway/integration` to `main` with `gh` and a `/pr`-format body. Evidence is the `check_cmd` output plus each ticket's Linear link. Merge Danger is the useful part: it's the same one-way-door judgment `research/01` names as a human touchpoint, now written down for Joe before he merges. Projects threads already write Before/After bodies, so it fits there too.

## /retro

User-invoked, reads a session's record, and proposes environment fixes (navigation pointers, lint rules or tests for repeated mistakes, `CODING_STANDARDS.md` for judgment calls, cuts to `AGENTS.md`/`CLAUDE.md`). It edits nothing until Joe picks a candidate. This is the learning loop `research/01` marks as missing ("Not measured. Nothing turns a correction into a check").

**Change:** after a real project's run, or weekly, Joe runs `/retro` over the last N Runway sessions, especially tickets that parked as `needs-human` or needed a retry. Its fixes go into the target repo, so the next Runway run gets them for free. Retry and park counts are the metric it should push down. **(unverified)** where headless `claude -p` runs leave their transcripts: each ticket runs in its own worktree path, so the logs are probably spread across several project folders under `~/.claude/projects`, and `/retro` may need pointing at them. Check on the next run.

## What the update breaks

- **`CONTEXT.md` becomes `GLOSSARY.md`** (and `CONTEXT-MAP.md` becomes `GLOSSARY-MAP.md`). The pm plugin reads `CONTEXT.md` in two places: `pm/skills/discovery/SKILL.md:17` and `pm/skills/whats-next/SKILL.md:29`. After the update, Matt's skills write `GLOSSARY.md` and those two pm skills stop seeing it. Update them to read either name, and run the `git mv` in each PM Dev project that has a `CONTEXT.md`. The two sandbox repos here have none.
- **`/resolving-merge-conflicts` is removed.** Nothing in pm or Runway references it. Delete it by hand if `npx skills update` leaves it.
- The approved skills folder on the Mac is `mattpocock-skills/1.2.2`, so Joe looks to be on 1.2.2 (inferred from the path).

## Suggested order

1. Patch pm's two `CONTEXT.md` references, then update the skills.
2. Add the finish step to Runway: review pass, then a draft PR with a `/pr` body. Add `/tdd` to `RUN_PROMPT`.
3. Run the next real low-stakes project through it, then `/retro` over its sessions and record what it found in experiment 01's results.
