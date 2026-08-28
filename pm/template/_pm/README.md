# _pm/ — personal project log

Per-person operational log. **Never authoritative**: `docs/` and the tracker
carry the shared truth; this folder records *what I did and what I'm doing*.
If `_pm/` disagrees with the tracker, the tracker wins. (The rule and the
stage chain: the pm plugin's `WORKFLOW.md`.)

The `_` prefix groups it at the top of the listing and signals "container,
not a working folder" — same convention as code-surface containers
(`_app/`, `_ws/`).

## What's inside

| File/folder | Purpose |
|---|---|
| `skeleton.md` | The macro why — Wei Hao's 5-step. Always populated, even if just a paragraph. |
| `sessions/` | Per-day, per-person files: `YYYY-MM-DD-<name>.md`. Intent block at the top, Shipped / Tried-Learned-Decided / Intent-vs-outcome at close. Append-only. |
| `transcripts/`, `artifacts/`, `prototypes/`, `deliverables/` | Created on first write — see the taxonomy in the root `CLAUDE.md`. |

## How the daily skills use it

- **`whats-next`** (morning) reads intents, the tracker frontier, and recent
  sessions; drafts today's Intent block into your session file.
- **`checkpoint`** (mid-session, at a consequential result) adds a dated
  re-aim under the Intent and pushes the change into the affected tickets.
- **`stepping-away`** (close) writes the session entry, settles the tracker,
  and compares Intent to outcome.

`_pm/` is portable: internal references stay local; outward references reach
`../docs/`, which exists in every stamped project.
