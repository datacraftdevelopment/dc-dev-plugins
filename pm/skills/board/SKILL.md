---
name: board
description: Render the current work of a pm-scaffolded repo as one read-only HTML page — inbox, intents, and every ticket under .scratch/*/issues/, ordered by what needs attention. Use when the user says "show me the board", "render the board", "what's on the board", "where are we", or wants to see the tracker at a glance. One file per repo, always overwritten, never a history. Not a tracker and not an editor — edit the markdown, rerun.
---

# board

A picture of the tracker you already have. One dependency-free script reads the pm
files and writes one HTML page. No server, no watcher, no model in the loop: the
agent's whole job is to run the command and open the result.

## Run it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/board/scripts/board.py" <repo-root>
```

Default root is the current directory. Output is always `<repo>/_pm/board.html`.
Open it in the Browser pane, or with `open`. Runs in under a second.

## What it reads

| Source | Becomes |
|---|---|
| `docs/intent/inbox.md` lines | Inbox section |
| `docs/intent/*.md` (not inbox or README) | Intents section, with `**Status:**` and `**Size:**` if present |
| `.scratch/<effort>/issues/*.md` | One section per effort; the map's `## Destination` paragraph under the heading |

Each ticket's state is computed from its header lines, not typed anywhere:

- **needs human** — `Status: needs-human`, or a `Waiting on:` / `Waits on:` line that isn't "nothing"
- **in progress** — `Status: claimed` or `in-progress`
- **ready** — open and every `Blocked by:` number is resolved
- **blocked** — open with an unresolved blocker; the blockers are listed under the row
- **done** — `resolved`, `done`, `closed`, `shipped`

Rows sort in that order inside each effort, then by number. Every row links to its
file.

## Rules

- **One file per repo.** `_pm/board.html`, overwritten every run. No dated copies, no
  history. The git log of the markdown is the history.
- **Gitignored.** The scaffold template ignores `_pm/board.html`. In a repo scaffolded
  before 0.22, add that line to `.gitignore` the first time you render there.
- **Read-only.** If the board looks wrong, fix the ticket file. Never edit the HTML.
- **Don't grow it.** No drag, no filters, no write-back, no live reload. If the need
  for those becomes real, that is the moment to evaluate a real board product, not the
  moment to extend this script.
