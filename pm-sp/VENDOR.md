# Vendored: four of Matt Pocock's skills

pm-sp carries four skills from Matt Pocock's pack that Agent Runway has nothing
like, so a pm-sp machine installs no other skill pack. Each copy is upstream
text except the changes listed, and each change is marked `pm-sp` in place.

Until 0.3.0 pm-sp also carried a trimmed copy of Jesse Vincent's Superpowers
and Matt's `wayfinder`, `grilling` and `prototype`. They're gone: the
agent-runway plugin carries the workflow now (its own `grill`, `prototype`,
`map` and `spec`, and six Superpowers skills behind its `hands-on` skill, with
their licence in its own `VENDOR.md`).

## Matt Pocock's skills

From **mattpocock/skills** (<https://github.com/mattpocock/skills>), MIT
licensed (`LICENSE.mattpocock`).

- **Upstream:** commit `5beb35b` (2026-10-19); the skills are identical to
  release 1.3.1.
- **Copied** (git-tracked files only, without the Codex `agents/openai.yaml`
  files): `domain-modeling`, `codebase-design`, `research`, `pr` (with its
  `CREDITS.md`, which credits Dex Horthy's `show-me`).
- **Left out:** everything else, including the ticket-per-session flow
  (`to-spec`, `to-tickets`, `implement`, `implement-spec`, `triage`), `tdd`,
  `diagnosing-bugs`, `code-review`, `grill-me`, `handoff`, `retro` and
  `setup-matt-pocock-skills`. Agent Runway's skills do those jobs.

### What was changed, and only this

1. `research` and `codebase-design`'s design-it-twice name their models
   (`sonnet` to read, `opus` for design), never the inherited session model.

`design-handoff` is not vendored: it is Joe's own, copied from this
marketplace's `design-dc` plugin (0.2.2) with a pm-sp section on where it
sits and the handoff path moved to `docs/specs/`. `design-dc` stays its
source; carry fixes across by hand.

## Updating from upstream

Roughly monthly, or when a release note matters: clone mattpocock/skills at
its new release, diff the four skills against `5beb35b`, apply upstream
changes keeping the one listed above, update the commit line, bump pm-sp's
version and run `python3 -m pytest tests/test_pm_sp_plugin.py -q` from the
marketplace root.
