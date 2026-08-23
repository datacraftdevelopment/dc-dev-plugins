---
name: dashboard
description: Render _pm/dashboard.html — a local-only stage board showing where each piece of work is (Discover → Chart → Spec → Ticket → Build → Verify → Ship → Learn), derived entirely from artifacts — docs/intent/, the wayfinder map, spec and tickets on the tracker, merges — plus today's Intent and recent sessions. Use when the user says "dashboard", "stage board", "where are we", "what stage is this at", "show me the board" — and as the closing refresh of whats-next, checkpoint, and stepping-away.
---

# Dashboard — the stage board

One HTML file the user opens to answer "what stage is each piece of work at, what's done, what's next" — without git, GitHub, or asking an agent. It is the **visibility layer** of the pm plugin (see `WORKFLOW.md`): Matt's skills are the verbs, this page shows the nouns.

**On probation.** If this page isn't being opened, it gets deleted. It earns its place only by being derived and never lying.

## The two rules

**1. Render, never source.** `_pm/dashboard.html` is derived output. Canonical state lives in `docs/intent/`, the tracker, `docs/adr/`, and `_pm/sessions/`. Never read project state *from* this file; never hand-edit beyond the island swap. Regenerate freely — idempotent, last render wins.

**2. Derive, never ask.** Every stage on the board comes from which artifacts exist. There is no field a human updates. If a stage can't be derived, it isn't shown — don't guess, don't prompt.

**Local-only.** The rendered file must not be committed (a JSON island is a merge-conflict machine in a team). If the project is a git repo, ensure `_pm/dashboard.html` is in `.gitignore` — add the line if it's missing. The *rules* in this skill are what's shared; every machine renders its own page.

## Checklist

**1. Stamp the template if needed.** Ships next to this file as `dashboard-template.html`. Copy to `_pm/dashboard.html` when missing, or when its `data-template-version` differs from the shipped one. Overwriting wholesale is always safe.

**2. Enumerate streams — one per intent.** Read every `docs/intent/*.md` (skip none; newest first). Per intent: title, status line (draft / accepted / superseded), the size call, author. Superseded intents are dropped from the board. No `docs/intent/` → the board shows "no intents yet — start with discovery".

**3. Derive each stream's stage.** Walk the chain and stop at the first stage that isn't done:

| Stage | Done when | How to check |
|---|---|---|
| discover | intent status is `accepted` (draft → stage is *discover*) | intent header |
| chart | wayfinder map exists and is cleared (all child tickets closed) — *skipped for one-session* | tracker: map issue labelled `wayfinder:map` referencing the intent; or `.scratch/<name>/` map file |
| spec | spec exists on the tracker (issue/file from `/to-spec` referencing the intent or map) — *skipped for one-session* | tracker search / `.scratch/` |
| ticket | implementation tickets exist (from `/to-tickets`) — *skipped for one-session* | tracker: issues referencing the spec |
| build | all implementation tickets closed, or (one-session) a branch/commits reference the intent | tracker + `git log --grep=<slug>` |
| verify | review evidence exists — PR has review / test output pasted in the last session entry | `gh pr list`/`gh pr view`; latest session file |
| ship | merged to main / deployed | `gh pr list --state merged`, `git log main` |
| learn | a later `docs/intent/` entry cites this one as source (incident → new intent) | intent `Source:` lines |

Stage = the first row not done. A one-session stream with no tickets sits at *build* until commits land, then *verify*, then *ship*. Record a one-line `next` per stream — the concrete thing that advances it (the frontier ticket to take, "open the PR", "run verify-before-done").

**4. Gather the map and tickets — read-only, degrade gracefully.** For multi-session streams collect the wayfinder map (destination, fog, out-of-scope, decisions so far, frontier / in-session / blocked with `wayfinder:<type>` labels, closed/open counts) and, once charted, the implementation tickets (open with claimant and blockers, closed count). Tracker unreachable (no auth, wrong account, offline)? Two tries max, then set `"wayfinder": {"available": false, "note": "<why>"}` and render from local artifacts only.

**5. Gather the personal layer.** Today's / latest `_pm/sessions/*.md` — Intent block and latest re-aim; newest 3 session files as one-line gists with author (from the filename's `-<name>` suffix, else "me"). Newest 5 `docs/adr/*.md` as decisions. `_pm/skeleton.md` for project name + one-liner.

**6. Build the JSON and swap the island.** Replace the whole content of `<script type="application/json" id="pm-data">…</script>` per the schema below. Escape literal `</` inside strings as `<\/`. Touch nothing else.

**7. Verify and hand over.** Confirm the island parses (`python3 -c 'import json,sys; json.load(sys.stdin)'`). Tell the user the path; offer to `open _pm/dashboard.html`. As a ritual's closing step, skip the offer — "board refreshed."

## Schema (v2)

Every field optional — the page hides empty sections. Dates `YYYY-MM-DD`; `generatedAt` ISO 8601 with timezone (the page computes staleness).

```json
{
  "schema": 2,
  "generatedAt": "2026-08-23T15:00:00-04:00",
  "generatedBy": "pm dashboard v2",
  "project": { "name": "", "oneLiner": "" },
  "sources": ["docs/intent/", "github:owner/repo", "_pm/sessions/"],
  "intent": { "date": "", "text": "", "reAim": "14:30 — …" },
  "streams": [ {
    "slug": "", "title": "", "intentPath": "../docs/intent/<slug>.md",
    "status": "draft|accepted", "size": "one-session|multi-session", "owner": "",
    "stage": "discover|chart|spec|ticket|build|verify|ship|learn",
    "next": "one line — what advances this stream",
    "spec": { "title": "", "url": "" },
    "map": {
      "title": "", "url": "", "destination": "",
      "closedCount": 0, "openCount": 0,
      "inProgress": [ { "title": "", "type": "grilling", "url": "", "claimedBy": "" } ],
      "frontier":   [ { "title": "", "type": "research", "url": "" } ],
      "blocked":    [ { "title": "", "type": "task", "url": "", "blockedBy": [""] } ],
      "fog": [""], "outOfScope": [""],
      "decisions": [ { "title": "", "url": "", "gist": "" } ]
    },
    "tickets": { "closedCount": 0, "openCount": 0,
      "open": [ { "title": "", "url": "", "claimedBy": "", "blockedBy": [""] } ] }
  } ],
  "wayfinder": { "available": true, "note": "only when false — why" },
  "sessions":  [ { "date": "", "by": "", "gist": "" } ],
  "decisions": [ { "date": "", "title": "", "gist": "", "path": "../docs/adr/….md" } ]
}
```

Keep it a glance: newest 3 sessions, newest 5 decisions, one-line gists.

## Ritual contract

`whats-next`, `checkpoint`, and `stepping-away` each end by refreshing the board (silently — derived, no approval). The page's staleness badge announces when no ritual has run.

## What this skill does NOT do

- Doesn't write to the tracker — read-only, always.
- Doesn't record state. A wrong stage means a missing or mis-labelled artifact — fix the source, re-render.
- Doesn't read `_pm/TASKS.md`, `_pm/decisions/`, or `_pm/context-map.md`. Pre-0.8 projects carrying them: see `MIGRATION-0.8.md`.
- Doesn't edit the template inline; template changes ship with the plugin (new `data-template-version`).
- Doesn't open the browser during ritual runs, and doesn't block on a broken tracker.
