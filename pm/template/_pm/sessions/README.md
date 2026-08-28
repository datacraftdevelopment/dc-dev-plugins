# Sessions

One file per working day **per person**: `YYYY-MM-DD-<name>.md` (`<name>` =
your short handle). Per-person and append-only, so two people on the same day
never collide and the log never needs merging. Captures what shipped AND the
thinking behind it — tried, learned, decided, dead-ended.

## Workflow

- **Starting a day:** `whats-next` creates today's file from
  [`_template.md`](_template.md) and drafts the Intent block.
- **Mid-day pivot:** `checkpoint` adds a dated re-aim line under the Intent —
  each re-aim is appended; the latest one is the live aim.
- **End of day:** `stepping-away` writes Shipped / Tried-Learned-Decided /
  Intent-vs-outcome and settles the tracker.
- **Empty days don't need a file.**

Durable decisions don't live here — they go to `docs/adr/`. Sessions are the
narrative; the tracker and `docs/` are the truth.
