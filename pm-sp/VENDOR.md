# Vendored: Superpowers and Matt Pocock's skills

pm-sp carries what it uses from two outside packs, so a pm-sp machine installs
no other plugin. Each copy is upstream text except the changes listed, and
each change is marked `pm-sp` in place.

## Superpowers

pm-sp carries a trimmed copy of Jesse Vincent's **Superpowers**
(<https://github.com/obra/superpowers>), MIT licensed (`LICENSE.superpowers`).

- **Upstream:** v7.0.1, commit `2ce8aa1` (2026-10-21).
- **Copied** (git-tracked files only, via `git archive`): `brainstorming`,
  `writing-plans`, `subagent-driven-development`, `executing-plans`,
  `finishing-a-development-branch`, `using-git-worktrees`,
  `requesting-code-review`, `receiving-code-review`, `test-driven-development`,
  `systematic-debugging`, `verification-before-completion`,
  `dispatching-parallel-agents`.
- **Left out:** `using-superpowers` and the SessionStart hook that injects it
  (the "even a 1% chance, you MUST invoke a skill" rule that takes over every
  session), `writing-skills`, `diagnosing-superpowers`, and
  `systematic-debugging`'s pressure-test and creation-log files (they test the
  skill, they don't run it).

### What was changed, and only this

1. Cross-references `superpowers:<skill>` became `pm-sp:<skill>`; the one
   reference to `writing-skills` became plain prose; `executing-plans` no
   longer points at `using-superpowers/references/`.
2. Paths: `docs/superpowers/specs/` → `docs/specs/`, `docs/superpowers/plans/`
   → `docs/plans/`. The gitignored working directory `.superpowers/` (ledgers,
   review packages, mockups) is unchanged, to keep upstream merges easy.
3. `brainstorming`: a calmer description (no "You MUST use this before any
   creative work"); the design doc gains an `## Acceptance` section in the
   `- [ ] A1: …` form `ship-acceptance` reads; a pm-sp second-opinion step after
   the builder check; and after the design is approved it **asks** whether to
   plan now instead of going straight to `writing-plans`.
4. `writing-plans`: an optional `## Lanes` section for `nested-sessions`.
5. `finishing-a-development-branch`: Step 1b, a pm-sp second-opinion on the
   branch before the options.

Everything else is upstream text. Search for `pm-sp` in the copied skills to
see each change in place.

## Matt Pocock's skills

From **mattpocock/skills** (<https://github.com/mattpocock/skills>), MIT
licensed (`LICENSE.mattpocock`).

- **Upstream:** commit `5beb35b` (2026-10-19); the seven skills are identical
  to release 1.3.1.
- **Copied** (git-tracked files only, without the Codex `agents/openai.yaml`
  files): `wayfinder`, `grilling`, `domain-modeling`, `codebase-design`,
  `prototype`, `research`, `pr` (with its `CREDITS.md`, which credits Dex
  Horthy's `show-me`). `templates/issue-tracker-github.md` is his
  `setup-matt-pocock-skills` GitHub tracker doc, without its PR-triage
  section.
- **Left out:** the ticket-per-session flow (`to-spec`, `to-tickets`,
  `implement`, `implement-spec`, `triage`), the parts Superpowers already
  covers (`tdd`, `diagnosing-bugs`, `code-review`), `grill-me`, `handoff`,
  `retro`, `setup-matt-pocock-skills` and the rest.

### What was changed, and only this

1. `wayfinder`: the missing-tracker hint points at `/pm-sp:scaffold`; a
   paragraph makes pm-sp's usual destination a set of chunks in order, each
   brainstormed in its own session; and a session may take the next ticket
   after recording the last, instead of one ticket per session; research
   findings go where the tracker doc says (pm-sp's local tracker keeps maps,
   tickets and research in `docs/maps/<effort>/`), not on a throwaway branch.
2. `prototype`: the context pointer goes in the design doc or the wayfinder
   ticket, not an implementation issue.

## The visual companion

Brainstorming's browser companion (`skills/brainstorming/scripts/`) runs a
small local server. Its page loads the Superpowers logo from primeradiant.com,
which tells the author which version is in use and nothing about the project.
Set `SUPERPOWERS_DISABLE_TELEMETRY=1` (or Claude Code's `DISABLE_TELEMETRY`) to
turn that off. It needs a local browser, so it works on the Mac and not in a
cloud session.

## Updating from upstream

Roughly monthly, or when a release note matters:

1. Clone each upstream at its new release and diff its copies of the skills
   above against the previously vendored commit.
2. Apply upstream changes here, keeping the changes listed above.
3. Update the commit line at the top, bump pm-sp's version, run
   `python3 -m pytest tests/test_pm_sp_plugin.py -q` from the marketplace root.
