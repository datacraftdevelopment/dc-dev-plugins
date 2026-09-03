# Intent: pm 0.11 — the ritual unit is the session, not the day

Author: Joe (with Opus). Status: accepted. Date: 2026-09-03.
Source: working session 2026-09-03 — Joe's observation that the rituals had
drifted out of alignment with how he actually works.

## Problem

`whats-next` shipped as a "morning open" and `stepping-away` as an
"end-of-day close." Neither describes what they're used for. Joe opens and
closes several sessions a day — the loop is wayfinder-shaped, each pass
restating an Intent for that pass — and he keeps sessions deliberately short
to hold the model in its smart zone. The day framing wasn't just odd
vocabulary; it was load-bearing and wrong in one place that mattered:
`_pm/sessions/` was **one file per person per day**, so a second session had
nowhere to put its own Intent, and `stepping-away` compared a whole day's
work against a single morning Intent.

Secondary finding: `checkpoint` — the mid-session re-aim — has never once
been used. Its drift check and its tracker push are already `stepping-away`
steps 2 and 3, and in a short-session workflow the real re-aim mechanism is
closing the session and opening a new one with a fresh Intent. It survived
0.10's "justify or delete" rule only narrowly.

## Proposed outcome

A 0.11.0 release where the session is the unit end to end.

Decisions made 2026-09-03:

- **One file per session, per person.** The day's first session keeps
  `YYYY-MM-DD-<name>.md`; later ones take an ordinal (`-2`, `-3`). Existing
  files stay valid unchanged as session 1. Each session owns one Intent, one
  close, one Intent-vs-outcome.
- **Reframe both rituals** — `whats-next` is the session open,
  `stepping-away` the session close. "Done-for-today" becomes
  "done-for-this-session"; the Intent is scoped to one session's work.
- **Keep `checkpoint`, demoted** rather than deleting it. It now opens by
  saying the session boundary is the preferred re-aim, and scopes itself to
  sessions that *can't* be closed and reopened: a wayfinder charting run
  mid-flight, a task already running, context too expensive to rebuild.
- **No session-size policing.** Considered adding a "smart zone" check to
  `checkpoint` that would recommend closing out when a session sprawled;
  rejected — judgment about session length stays with Joe, and the rituals
  should stop pretending to be daily, not start nagging.

## Not in scope

Skill names stay (`whats-next` / `stepping-away` / `checkpoint` were never
the problem — the framing inside them was). No change to the stage chain, the
`docs/` vs `_pm/` rule, the gate schedule, the scaffold, or the
credential-guard hook.

## Touched

`pm/skills/{whats-next,stepping-away,checkpoint}/SKILL.md`,
`pm/template/_pm/{README.md,sessions/README.md,sessions/_template.md}`,
`pm/template/{CLAUDE.md,README.md}`, `pm/{README.md,WORKFLOW.md}`,
`pm/commands/pm-scaffold.md`, both plugin manifests.
