---
name: checkpoint
description: Mid-session re-aim — fires at a consequential checkpoint (evidence just overturned an assumption, the direction changed, a milestone landed, a long-running task is about to continue on a stale brief) or when the user says "checkpoint", "re-aim", "refresh the state", "update the intent before we keep going". Rewrites the stale parts of the current state so work not yet done inherits the newest judgment. NOT the morning open (whats-next) and NOT the end-of-day close (stepping-away).
---

# Checkpoint

The mid-day beat between `whats-next` and `stepping-away`. The opening brief ages while the work teaches you what the job actually is; this skill makes the correction reach the work that hasn't happened yet, instead of dying in conversation. Done when the state **describes the present rather than narrating how we got here**.

Agents on long-running or multi-session work: run this **unprompted** whenever a consequential result lands — don't wait to be asked. It's cheap, and hour four should benefit from what hour three taught.

## Checklist

**1. Name what changed.** One sentence: which assumption, direction, or result made the current state stale. **If nothing consequential changed, say so and stop** — this ritual run on noise is how state files rot.

**2. Re-aim the Intent — don't overwrite it.** In today's `_pm/sessions/YYYY-MM-DD.md`, leave the original Intent block as written (stepping-away's drift check needs it) and add a dated re-aim line beneath it, replacing any earlier re-aim from today:

> **Re-aimed 14:30:** evidence X replaces the buyer assumption — done-for-today is now Y; Z drops out of scope.

The latest re-aim is the live aim; the morning Intent stays as the record of where the day started.

**3. Push the change into unfinished work.** `_pm/TASKS.md`: update any Current item whose Why / Done-when the change invalidates; demote or rewrite Next items now aimed at the wrong thing. Name what you touched.

**4. Archive, don't delete.** A replaced decision that still explains the project gets a `_pm/decisions/` entry (status: superseded, linked both ways) or a line in today's Tried / Learned / Decided. Preserve hard constraints exactly; don't let a preference quietly harden into a rule — or a rule soften into a preference.

**5. Map only if sources changed.** Touch `_pm/context-map.md` only when a source's authority, freshness, exclusion, or load-trigger actually changed. Most checkpoints don't.

**6. Show before writing.** Short before/after of the re-aim and any TASKS lines. Then write.

**7. Refresh the dashboard.** The re-aim just changed the live state — if `_pm/dashboard.html` exists (or the `dashboard` skill is available), regenerate it so the page shows the re-aim. Silent; skip if the project has no dashboard.

## What this skill does NOT do

- Doesn't open the day (`whats-next`) or close it (`stepping-away`).
- Doesn't rewrite the morning Intent in place — the re-aim line *is* the deliberate-pivot record; erasing the original hides drift.
- Doesn't append a diary. Replace stale state; keep the file scannable.
- Doesn't auto-commit.
