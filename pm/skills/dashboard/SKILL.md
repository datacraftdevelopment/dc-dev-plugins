---
name: dashboard
description: Regenerate _pm/dashboard.html — a self-contained visual status page (today's Intent, wayfinder map with frontier/blocked/fog, tasks, milestones, recent sessions and decisions) rendered from project sources. Use when the user says "dashboard", "update the dashboard", "show me where we're at", "open the dashboard" — and as the closing refresh step of whats-next, checkpoint, and stepping-away.
---

# Dashboard

One HTML file in `_pm/` the user double-clicks to see where the project is — without git, without GitHub, without asking an agent. It is the solo/local visibility surface: every agent on this machine writes to the *sources* (`_pm/*.md`, the tracker), and any of them may re-render this page at any time.

## The one rule: render, never source

`_pm/dashboard.html` is **derived output**, like a build artifact. Canonical state lives in `_pm/*.md` and the issue tracker — never in this file.

- Never hand-edit it beyond the island swap described below; never read project state *from* it.
- Regenerate freely: it's idempotent, so concurrent sessions re-rendering is harmless — last render wins and is always reproducible.
- Recording state (TASKS updates, session entries, ticket resolutions) happens in the sources first; the render comes after.

## Checklist

**1. Stamp the template if needed.** The template ships next to this SKILL.md as `dashboard-template.html`. Copy it to `_pm/dashboard.html` when the file doesn't exist, or when its `data-template-version` attribute differs from the shipped template's. The file is derived — overwriting wholesale is always safe.

**2. Gather local state.** Read (skip whatever doesn't exist):

- `_pm/skeleton.md` — project name + one-liner
- Today's / latest `_pm/sessions/YYYY-MM-DD.md` — Intent block and any re-aim line (the latest re-aim is the live aim)
- `_pm/TASKS.md` — Current (with Why / Done-when), Next, Waiting on, Backlog
- Newest few `_pm/decisions/` entries; newest 2–3 session files for one-line gists
- `_pm/milestones/` subfolders (ignore `_template-milestone`) — name, state, one-line note

**3. Gather the wayfinder map — read-only, degrade gracefully.** Only if the project has a map (linked from TASKS/sessions, or found via the tracker, e.g. `gh issue list --label "wayfinder:map"`). Collect per map:

- Title, URL, **Destination** and the **Not yet specified** / **Out of scope** sections from the map body
- Open child tickets split by state: **frontier** (open, unblocked, unclaimed), **inProgress** (claimed — note the assignee), **blocked** (with the titles blocking them); each with its `wayfinder:<type>` label
- **Decisions so far** from the map body (title, link, one-line gist); closed/open counts

If the tracker is unreachable (no auth, wrong account, offline), don't retry more than twice and don't fail the run — set `"wayfinder": {"available": false, "note": "<why, in one line>"}` and render local state only.

**4. Build the JSON and swap the island.** Replace the entire content of `<script type="application/json" id="pm-data">…</script>` with fresh JSON per the schema below. Escape any literal `</` inside JSON strings as `<\/` (JSON-legal, HTML-safe). Touch nothing else in the file.

**5. Verify and hand over.** Confirm the island parses (`python3 -c 'import json,sys; json.load(sys.stdin)'` fed with the JSON). Tell the user the path; offer to `open _pm/dashboard.html`. When run as a ritual's closing step, skip the offer — just note "dashboard refreshed."

## Schema (v1)

Every field optional — the page hides empty sections. Dates are `YYYY-MM-DD`; `generatedAt` is ISO 8601 with timezone (the page computes staleness from it).

```json
{
  "schema": 1,
  "generatedAt": "2026-08-20T17:45:00-04:00",
  "generatedBy": "pm dashboard v1",
  "project": { "name": "Switchyard", "oneLiner": "Three-surface work tracker." },
  "sources": ["_pm/TASKS.md", "_pm/sessions/", "github:owner/repo issues"],
  "intent": { "date": "2026-08-20", "text": "…", "reAim": "14:30 — …" },
  "tasks": {
    "current": [ { "title": "", "why": "", "doneWhen": "", "note": "" } ],
    "next":    [ { "title": "", "note": "" } ],
    "waiting": [ { "title": "", "since": "2026-08-12", "note": "" } ],
    "backlog": [ { "title": "" } ]
  },
  "milestones": [ { "name": "", "state": "active|planned|done", "note": "" } ],
  "sessions":   [ { "date": "", "gist": "" } ],
  "decisions":  [ { "date": "", "title": "", "gist": "", "path": "decisions/….md" } ],
  "wayfinder": {
    "available": true,
    "note": "only when available is false — why, one line",
    "maps": [ {
      "title": "", "url": "", "destination": "",
      "closedCount": 0, "openCount": 0,
      "inProgress": [ { "title": "", "type": "grilling", "url": "", "claimedBy": "" } ],
      "frontier":   [ { "title": "", "type": "research", "url": "" } ],
      "blocked":    [ { "title": "", "type": "task", "url": "", "blockedBy": ["ticket title"] } ],
      "fog":        [ "one line per Not-yet-specified patch" ],
      "outOfScope": [ "one line each" ],
      "decisions":  [ { "title": "", "url": "", "gist": "" } ]
    } ]
  }
}
```

Keep lists tight: newest 3 sessions, newest 5 decisions, gists one line each. The page is a glance, not an archive — the sources hold the detail.

## Ritual contract

`whats-next`, `checkpoint`, and `stepping-away` each end by refreshing this dashboard (silently — it's derived, no approval needed). That wiring is what keeps the page trustworthy: it can only go stale if no ritual ran, and the page's staleness badge announces exactly that.

## What this skill does NOT do

- Doesn't write to the tracker — tracker access here is read-only, always.
- Doesn't record state. If you notice TASKS or a session entry is wrong, fix the source (or run the right ritual), then re-render.
- Doesn't edit the template inline. Template changes happen in the plugin (new `data-template-version`), then re-stamp.
- Doesn't auto-open the browser during ritual runs.
- Doesn't block on a broken tracker — degrade to local-only and say so in the island's `note`.
