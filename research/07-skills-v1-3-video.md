# Matt's v1.3 video against the factory

> Written 2026-10-06 from Matt Pocock's video "New Skills! v1.3 brings /pr, /implement-spec, and /retro" (https://www.youtube.com/watch?v=BsJGo1wFTvQ, about 19 minutes). `research/06` covered the same release from the changelog and the aihero.dev pages; this note only records what the video adds or settles.
>
> **Source caveat.** No YouTube transcript skill was found from this session (not among Joe's enabled claude.ai skills, not in the pm plugin, which only has `granola-transcript`; `~/.claude/skills` on the Mac isn't reachable from a folder thread). YouTube itself refused both the cloud container and the Mac's sandbox, so the transcript was read through a third-party transcript page (youtubetotranscript.com) and summarized here. Timestamps are approximate and the quotes are short; no verbatim transcript is stored. Re-check anything load-bearing against the video.

## Short answer

The video confirms the current design rather than changing it. Matt himself ranks a deterministic loop above `/implement-spec`'s sub-agent orchestration, and says `/retro` must stay human-run. Two small changes follow for `runway retro`, both recorded in `decisions.md`; nothing in Runway's code changes now.

## What the video adds

**1. Matt ranks the three ways to run tickets (≈2:00–4:00).** Manual loop (you drive each ticket), deterministic loop (a script drives them: "runs the same way every time", the most reliable and cheapest), and sub-agent orchestration (what `/implement-spec` does). He calls orchestration worse than a deterministic loop because the loop is deterministic, and offers `/implement-spec` as the accessible middle ground for people who won't build a loop. Runway is the deterministic loop, so this is the author of the skills backing `decisions.md` 2026-10-05 (script manager) and 2026-10-06 (keep Runway).

**2. `/implement-spec` has no human gates (≈3:45–4:30).** The video describes it as something you start, then step away while it implements the whole spec, merges each ticket to an integration branch, runs code review on that branch, and leaves one PR. No checkpoint between tickets is mentioned. That matches `research/06`'s reading; it's still **(unverified)** whether it skips `ready-for-human` tickets, so the advice to pause the launchd job before running it stands.

**3. `/pr` only writes the body, and it auto-invokes (≈6:45–9:00).** Sections: Summary (from Dex's "show me" idea), Evidence (before and after, screenshots or test runs; he frames it as how you learn to trust agent output, and the skill can prompt the agent to go run extra verification), Merge danger (one-way vs two-way door) and Blast radius. He says it's one of the most consistently model-invoked skills on Opus 5.5. Runway's `PR_PROMPT` already has all four (blast radius sits inside Merge danger). The auto-invoke point partly answers experiment 04's open question about whether `/pr` loads in headless `claude -p`: it likely does when `Skill` is allowed, still to be seen on the first real finish run.

**4. `/retro`: sample sessions, and never automate it (≈12:15–16:30).** It reads a coding-agent session (the current one, or ones from history) and looks for what the agent didn't complain about: how easy the codebase was to navigate, checks that could be automated, coding standards, `AGENTS.md`/`CLAUDE.md` health, tool economy, instructions that are no-ops, and information the agent couldn't reach. Two points are new against `research/06`:
- **Run it on a sample, not just the failures.** He suggests running it on a sampling of sessions whenever there's a free moment, plus the odd ones. `runway retro` today lists only the runs that struggled (and the latest runs only when nothing struggled), so clean-looking runs that quietly wasted tokens never get looked at.
- **Don't automate it.** An automated retro loops on its own false positives and drifts the setup. Runway already only writes a prompt for Joe to start; this makes it a rule not to schedule `runway retro` into launchd or apply its findings without Joe picking them.

**5. Retro should look at Runway's own prompts too.** "Instruction no-ops" and steering-file health apply to the factory itself: `RUN_PROMPT`, `REVIEW_PROMPT` and `PR_PROMPT` in `runway.py` steer every ticket. A retro over Runway sessions should be told those prompts exist so it can flag lines the agent ignores. (My inference, not something Matt says.)

**6. Glossary rename (≈10:30).** Same as `research/06`: domain modelling now writes a glossary file instead of `CONTEXT.md`, and other skills depend on it. Nothing new; the two pm references are still the to-do.

## Changes to make next (not done here)

Kept out of the code on purpose while the folder moves into `dc-dev-plugins/factory`:

1. `runway retro`: add two or three clean runs, picked at random from the log, to the flagged ones, labelled as a sample.
2. `runway retro`: name `experiments/01-runway/runway.py` and its prompt constants in the `/retro` prompt so instruction no-ops in Runway itself get flagged.
3. Optional, per repo: let the PR-body step ask for before/after evidence beyond `check_cmd` (a screenshot or a run of the app) for UI work. Today the prompt forbids claims the check output doesn't show, which is the safer default; leave it unless a client project needs it.
