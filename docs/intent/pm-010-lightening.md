# Intent: pm 0.10 — lighten the plugin, lazy scaffold, kill the drift

Author: Joe (with Fable). Status: accepted. Date: 2026-08-28.
Source: critical review session 2026-08-28 — Fable read + two-seat Ringer panel
(Codex + Sonnet); full record in `.review-gate/2026-08-28-pm-plugin-review/`.

## Problem

The plugin accreted through 0.5 → 0.9.3 and the seams show. Three verified,
both-seats findings: (1) `/pm:pm-scaffold` eagerly stamps ~20 opt-in folders
with `.gitkeep`s and stub READMEs while the two folders current doctrine needs
(`docs/intent/`, `docs/adr/`) aren't templated at all; (2) `template/` still
teaches the pre-0.8 doctrine (TASKS.md, context-map, shared single session
log) that the shipped skills explicitly refuse — every new project is born
legacy; (3) the credential-guard hook had five bypasses (fixed in this same
session, tests in `pm/hooks/test-credential-guard.sh`). Plus a tail of
verified sole-finder items: Granola's gitignore promise is false, the
dashboard's check command can't run, in-place mode contradicts itself, the
scaffold never `git init`s, SOUL.md ships into client-readable repos, and
`okf`/`granola-transcript` are unaccounted for in WORKFLOW's "justify or
delete" rule.

## Proposed outcome

A 0.10.0 release where: a fresh scaffold contains only what every project
uses on day one, with the full layout encoded as a taxonomy table
("created on first write, never pre-built"); no shipped doc contradicts
another; the template is designed in place in this repo. Decisions made
2026-08-28: **retire the DC-Project-Builder mirror** (dc-plugins is the
design home), **delete the dashboard skill** (probation called), **keep okf
and granola-transcript** with an explicit utility-skills clause in
WORKFLOW.md.

## Affected users and systems

`pm/` wholesale: template/ (reshaped), commands/pm-scaffold.md (rewritten),
skills/ (dashboard deleted; ritual skills drop board steps; granola path
promise fixed), WORKFLOW.md, README.md, MIGRATION-0.8.md, plugin.json
(0.10.0). Repo `CLAUDE.md` (mirror policy removed). One line in the global
`Agentic/CLAUDE.md` (visibility-layer phrase). Existing scaffolded projects:
unaffected until they choose to migrate; a short 0.10 migration note covers
them. DC-Project-Builder repo: dormant — retirement note is a follow-up
outside this repo.

## Constraints

Matt-primary doctrine unchanged: pm never re-absorbs planning/execution.
`docs/` shared / `_pm/` personal rule unchanged. Portable paths only
(`${CLAUDE_PLUGIN_ROOT}`); no machine paths in shipped files. Skill/command
names keep their namespaces. Version bump required to ship.

## Open questions

- Whether the retired builder repo gets archived to `xArchive/` or just a
  retirement note — Joe, outside this repo.
- Whether old projects bother migrating (the note is optional by design).

## Size call

One session → build it now, this session (plan is the review's
recommendation set; no wayfinder needed).
