---
name: checkpoint
description: Mid-session re-aim — a long wayfinder charting run, a background task about to continue on a stale brief, a session whose direction changed. Fires when a consequential result lands, or when the user says "checkpoint", "re-aim", "refresh the state", "update the intent before we keep going". NOT the session open (whats-next) and NOT the session close (stepping-away).
---

# Checkpoint

A checkpoint re-aims the session in place. Closing and reopening (`stepping-away` → `whats-next`) is a legitimate alternative when the thread is cheap to rebuild — but neither road is required, and this skill never demands the boundary. Re-aim in place whenever that loses less: a wayfinder charting run mid-flight, a long-running task that will continue whether or not you re-aim it, context expensive to rebuild, or simply a direction change worth recording without breaking stride. The opening brief ages while the work teaches you what the job actually is; the correction has to reach the work that hasn't happened yet instead of dying in conversation. Done when the state **describes the present rather than narrating how we got here**.

## Checklist

**1. Name what changed.** One sentence: which assumption, direction, or result made the current state stale. **If nothing consequential changed, say so and stop** — this ritual run on noise is how state files rot.

**2. Read the bound session file, its Intent and latest re-aim; reconcile against docs and the tracker. Re-aim the Intent — don't overwrite it.** In this session's file, `_pm/sessions/YYYY-MM-DD-<name>[-N].md`, leave the original Intent block as written (stepping-away's drift check needs it) and **append** a dated Re-aimed section at the end — earlier re-aims stay; the session file is append-only:

> **Re-aimed 14:30:** evidence X replaces the buyer assumption — done for this session is now Y; Z drops out of scope.

The latest re-aim is the live aim; the opening Intent and any earlier re-aims stay as the record of how the session moved.

**3. Push the change into unfinished work — on the tracker.** The change may invalidate an open ticket's premise, graduate a patch of fog into a ticket, or re-scope the map. Comment on the affected tickets (or update the local `.scratch/` map) so the next session inherits the correction; if the intent itself changed, edit `docs/intent/<slug>.md` and say so. Name what you touched. (A `TASKS.md` the repo hasn't declared its tracker: don't maintain it — `MIGRATION-0.17.md`.)

**4. Archive, don't delete.** A replaced decision that still explains the project gets a `docs/adr/` entry (status: superseded, linked both ways — `/domain-modeling` owns the format) or a line in this session's Tried / Learned / Decided. Preserve hard constraints exactly; don't let a preference quietly harden into a rule — or a rule soften into a preference.

**5. Show before writing.** Short before/after of the re-aim and any ticket comments. Then append via the bound path and ID:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/session.py" --root . reaim --session <bound-path> --id <bound-id> --entry-file <reaim-text-file>
```

A closed session rejects re-aim. A missing binding is recovered from this conversation, never the highest ordinal. For a legacy file explicitly identified by the user, append manually. An already-running unattended loop does not read personal logs: use `build-swarm`'s documented run-status and pause-request mechanism to bring it to a clean stop, reconcile the tracker/constraints, then restart — and promise a *clean* pause only after that mechanism has reported the run paused. Where that control isn't available for the run, say so and report the loop's existing caps instead of claiming a clean stop. Never edit active worker inputs mid-run.

## What this skill does NOT do

- Doesn't open the session (`whats-next`) or close it (`stepping-away`) — and doesn't compete with them. Closing and reopening remains available; neither road is required.
- Doesn't rewrite the session's opening Intent in place — the re-aim line *is* the deliberate-pivot record; erasing the original hides drift.
- Doesn't append a diary. A re-aim is one line; detail goes to the tickets. Keep the file scannable.
- Doesn't auto-commit.
