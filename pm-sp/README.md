# pm-sp: the light pm

Joe's personal layer on top of **Agent Runway**. The `agent-runway` plugin
carries the shaping (`grill`, `prototype`, `map`, `spec`) and the `hands-on`
skill with the Superpowers skills it builds with (plans, subagents, TDD,
debugging, verification). Runway itself is per repo: a repo that isn't added
to it never sees tickets or Runway suggestions, and the work runs in the
session. In a Runway repo, `file-tickets` can send well-fitting work to the
app, after one ask kept in the spec's front matter (`runway: yes|no`). pm-sp holds the session around it and adds what only Joe's
projects need. **Read [`WORKFLOW.md`](./WORKFLOW.md) first.**

pm-sp **requires agent-runway**. The Runway app installs agent-runway on its
first run (or `runway install-skills`); then:

```
/plugin install pm-sp@dc-dev-plugins
```

pm-sp is an alternative to `pm`, not an add-on: **install one or the other on
a machine, never both.** They share the credential-guard hook (it would run
twice) and several skill names (`whats-next`, `stepping-away`, `checkpoint`,
`ship-acceptance`, …). Don't install upstream Superpowers or Matt Pocock's
skills alongside it either: their flows compete with Runway's.

## What's in it

**The session layer (pm-sp's own):**

- `whats-next`: session open. Reads specs, plans and their ledgers, recent
  sessions, and (in a Runway repo) what Runway is running and which hands-on tickets wait; proposes
  the pick-up; writes the Intent.
- `stepping-away`: session close. Entry against the Intent, a resumable line
  per plan in flight, inbox capture, next-session offer.
- `checkpoint`: mid-session re-aim when the session can't break.
- `second-opinion`: Sol through Ringer plus a fresh Opus, on a project-sized
  spec (as its builders) and, when asked, on a finished branch.
- `ship-acceptance`: the spec's Acceptance checks against the real candidate
  and production, recorded in `docs/shipped/`.

**Screens (pm-sp's own, from design-dc):** `design-handoff` writes the brief
that takes a data sample into Claude Design, so the screens are shaped and
approved before anything is built.

**Four of Matt Pocock's skills Runway has nothing like** (vendored, see
[`VENDOR.md`](./VENDOR.md)): `domain-modeling` (glossary and ADRs),
`codebase-design` (deep modules), `research`, and `pr` for PR bodies.

**Guards and kits (from pm, unchanged in substance):**

- The **credential guard**: a `PreToolUse` hook on Bash that blocks staging or
  committing `.env`, key and certificate files. Always on. A copy of pm's;
  pm is the source.
- `gate-hooks`: opt-in per repo (production gate, protected paths, test lock).
  See [`GATES.md`](./GATES.md).
- `review-policy` with the read-only `policy-reviewer` agent.
- `ui-test`: agent-run UI tests for macOS apps under Ringer. See
  [`UI-TEST.md`](./UI-TEST.md).
- `granola-transcript`, `okf`: utilities.

**`/pm-sp:scaffold`** stands up a project from `template/`: `CLAUDE.md` with
the workflow rules, `docs/` (inbox, quirks, a note on where maps live; other
folders appear on first write), `_pm/` with the skeleton and sessions. It runs
the skeleton interview. Also adds a stack's plugins to a repo (`stack vercel`).

## What it assumes

- **The agent-runway plugin**, and the Runway app on the Mac that runs
  tickets. Shaping and the hands-on skills work in any session; filing and
  closing tickets need `runway`.
- **Ringer** and its library skills (`ringer`, `cross-review-gate`) on the Mac,
  for `second-opinion`'s Sol reader and `ui-test` (the marketplace README
  explains). Without them, second-opinion runs Opus alone and says so.
- **Python 3.9+** as `python3` on Claude Code's Bash PATH: the always-on
  credential guard and the session and delivery helpers need it (check with
  `python3 --version`). `ui-test` also needs Pillow (see `UI-TEST.md`).
- **git** with a remote, so maps, specs and plans travel between computers.

## Not carried over

From pm: `discovery`, `fast-grill`, `orchestrate`, `session-succession`,
`verify-before-done`, `board`, `runway`. Until 0.3.0 pm-sp also carried
Superpowers' workflow skills, `wayfinder`, `grilling`, `prototype` and
`nested-sessions`; `WORKFLOW.md` says where each went. Repos with
`docs/intent/` files still work with `ship-acceptance`; new projects put
acceptance in the spec.
