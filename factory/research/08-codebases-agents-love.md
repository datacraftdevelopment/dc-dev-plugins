# Deep modules and grey boxes, against the factory

> Written 2026-10-09 from Matt Pocock's article "How To Make Codebases AI Agents Love" (https://aihero.dev/how-to-make-codebases-ai-agents-love, updated 2026-02-26, about 700 words). Summarized here, not copied. The article's pitch is the `/improve-codebase-architecture` skill, which ships in Matt's skills 1.3.1 with `codebase-design` as its vocabulary; both were read from the 1.3.1 plugin cache in a cloud session.

## Short answer

The article is the "why" behind skills we already run (`codebase-design`, `/tdd`'s seams, `/to-spec`'s module sketch). Its one idea that changes the factory is the **grey box**: the human owns a module's interface, the agent owns its implementation, and tests at the interface keep the agent honest. Runway already does the second half. It doesn't yet say who owns the first half, and one line of its run prompt pulls against it.

## What the article says

- An agent is a new starter with no memory ("the guy from Memento"). The codebase, more than the prompt or `AGENTS.md`, decides the output.
- A badly shaped codebase costs three ways: slow feedback (the agent can't tell if its change worked), poor navigation (it can't find things or work out how to test them), and human burnout (you hold the whole web together by hand).
- The human has a mental map of grouped features; the agent sees a flat web of small modules that all import each other.
- Fix: **deep modules** (Ousterhout, *A Philosophy of Software Design*): lots of implementation behind a small interface, every export going through it, one folder per module, interface at the top (progressive disclosure).
- **Grey box modules:** design the interface carefully, delegate the inside to the agent, lock behavior with tests at the interface. Look inside only to apply taste or tune performance.
- The human then holds seven or eight chunks instead of hundreds of modules. Taste still applies at the boundaries, so this is "a million miles from vibe coding".
- Think about module boundaries from the PRD through to the implementation issues. Tests and feedback loops are how the agent knows its change works.
- TypeScript makes the boundaries hard to enforce; Matt leans on Effect for it. Nothing new: this is twenty-year-old good practice.

## How it maps onto the factory

**Runway is the grey box's "agent owns the implementation" half.** Each ticket runs unattended in its own worktree, test-first, and the finish step reviews the whole branch. What the article adds is that the interface is the human's part. Today nothing in Runway's gating rule or prompts says so.

**The `/tdd` seam rule doesn't fit a headless run.** `RUN_PROMPT` tells every run to use `/tdd`. In 1.3.1, `/tdd` says "Test only at pre-agreed seams... confirm them with the user. No test is written at an unconfirmed seam." A Runway run has no user. It either writes `RUNWAY_QUESTION.md` and parks a ticket that was meant to run, or ignores the rule and picks seams itself, which is exactly the part the article says the human owns. The grey-box answer is that the seams get agreed upstream: `/to-spec` already sketches "the seams at which you're going to test the feature" and lists modules and their interfaces, with the user, so the run should test at the seams the ticket or spec names and stop only when it needs a new or changed interface. **(Inferred from reading both skills; not yet seen in a run log.)**

**The gating rule has no bucket for an interface change.** The four buckets send "an architecture choice that takes more than a session to unwind" to Joe. A new module, or a changed public interface, is the grey-box boundary, but may be quick to unwind, so it lands in "Technical" and runs unattended. Adding "a new module or a changed module interface" to the gated buckets would match the article; it would also put more tickets in front of Joe, which is the bottleneck the factory exists to shrink.

**`worker-env.md` is the navigation half for one repo.** It already covers feedback loops (the Verify command) and paths to leave alone. A short "Modules" list (each deep module's folder and its interface file) would give a fresh run the map the article says it lacks. Cheap, but only worth it in repos that actually have that shape.

**Runway is itself a candidate.** `runway.py` is about 2,000 lines in one file, with the trackers behind adapters (`github_tracker.py`, `linear_tracker.py`): two adapters, which `codebase-design` counts as a real seam. Running `/improve-codebase-architecture` on `factory/plugin/runway/` would show whether the rest (queue, finish step, Ringer panel) wants the same treatment. It's human-started and grills you through one candidate, so it's a session for Joe, not a ticket.

**FileMaker work (fm-dc) is the hard case.** The article's tools are folders and type signatures. A FileMaker solution has neither in a form an agent reads easily, so "deep modules" there means script and layout conventions, not file layout. Not explored here.

## Changes it suggests

1. Make `RUN_PROMPT` say where seams come from, so `/tdd` doesn't stall or freelance in a headless run. In line with existing decisions (runs use `/tdd`; the agent builds, Joe decides), so filed as an issue.
2. Add "new module or changed interface" to the gating rule's gated buckets. Joe's call: it trades unattended runs for control of the boundaries.
3. Add an optional "Modules" section to the `worker-env.md` template. Joe's call; small.
4. Run `/improve-codebase-architecture` on `factory/plugin/runway/`. Joe's call; a hands-on session.
