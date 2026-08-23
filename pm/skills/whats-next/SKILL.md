---
name: whats-next
description: Morning open — propose 1-2 things to pick up AND draft today's Intent block (the agent's anchor for the day). Use when the user says "what's next?", "what should I work on?", "where did we leave off?", "catch me up," or starts a session cold without a specific task in mind.
---

# What's Next

Morning open. The user is starting a session — could be future-them four days later, or a teammate cold-starting. Ground the answer in context, not vibes, and **draft an Intent block** they can paste into today's session entry to keep the agent oriented during execution.

**Don't ask "what do you want to work on?"** That's what they're asking *you*. Read first, then propose.

## Checklist

**1. Read.** Shared record first, personal log second (`WORKFLOW.md`: `docs/` is truth, `_pm/` is log).
- `docs/intent/*.md` — every open intent (status draft/accepted): these are the streams of work. Note each one's size call.
- **The tracker** — the frontier: open wayfinder tickets (unblocked, unclaimed) and open implementation tickets. GitHub: `gh issue list --label wayfinder:map`, then children; local: `.scratch/<name>/`. Unreachable → say so, go on with local artifacts.
- `docs/adr/` newest entries, `CONTEXT.md` if present — what's been decided.
- `_pm/skeleton.md` — the macro why of the project.
- Last 1–3 session files in `_pm/sessions/` (any author, most recent first) — especially Open threads and yesterday's Intent-vs-outcome.
- `knowledge/index.md` — only if a knowledge bundle exists. Skim; don't crawl.
- **Legacy (pre-0.8 projects only):** if `_pm/TASKS.md` exists, read it as a hint, not a source of truth — anything on it that matters belongs on the tracker. Don't grow it. See `MIGRATION-0.8.md`.

**2. Propose.** Output:

```
Where we are: <one sentence — which streams exist and what stage each is at>.
Frontier: <takeable tickets, or "nothing charted yet">.
Recommended pick-up: <one specific ticket / next stage step> — because <reason tied to context>.
Also worth: <maybe one more>.
Watch-outs: <claimed tickets gone quiet; open threads worth surfacing; an intent still in draft>.
```

**3. Draft the Intent block** for the most likely pick-up. Two or three sentences of plain prose — what we're pushing on, why it matters, what done-for-today looks like, anything explicitly not in scope. Example:

> Pushing on the search filter UI today — Sandy's manual workaround is costing her ~20 min/day, and a working filter unlocks the rest of the search flow. Done-for-today is the prototype validated by Sandy via parrot-back. Not touching filter persistence or multi-category yet.

**4. Wait.** Don't start the work. The user picks AND confirms (or amends) the Intent. It's their commitment for the day.

**5. Write.** Once approved, write the Intent block into today's session file: `_pm/sessions/YYYY-MM-DD-<name>.md` — per person, so two people on the same day never collide (`<name>` = the user's short handle; ask once if unknown, then remember it in the project `CLAUDE.md`). Create from `_pm/sessions/_template.md` if needed. Shipped / Tried-Learned-Decided sections stay empty until end-of-day. If the stream's wayfinder ticket is what's being picked up, **claim it on the tracker** (assign to self) — the assignee is the claim.

**6. Refresh the board.** If the `dashboard` skill is available, regenerate `_pm/dashboard.html` per that skill so the stage board opens on today's Intent. Silent — derived; no approval needed.

## When the project has no history

Brand-new project: propose drafting the skeleton (if still placeholder), or running `discovery` on the first piece of work so there's an intent to stand on. Still draft an Intent block — the push that day IS "draft the skeleton" or "discover the first stream."

## Why this skill matters

> "These systems were built to execute. They nail the *what* and quietly let the *why* go." — Matt Maher

The Intent block is the why-of-the-day, written where the agent reads it on every tool call. Without it, the agent has the queue but no orientation.
