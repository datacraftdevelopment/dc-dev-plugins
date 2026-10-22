# pm-sp: pm on Superpowers

Joe's project-management layer, rebuilt around Jesse Vincent's
[Superpowers](https://github.com/obra/superpowers) as the main workflow.
Superpowers' skills do the work (brainstorm, design, plan, run the plan in one
session with subagents, finish the branch); pm-sp's skills hold the session
around it. **Read [`WORKFLOW.md`](./WORKFLOW.md) first.**

pm-sp is an alternative to `pm`, not an add-on: **install one or the other on
a machine, never both.** They share the credential-guard hook (it would run
twice) and several skill names (`whats-next`, `stepping-away`, `checkpoint`,
`ship-acceptance`, …). Don't install upstream Superpowers or Matt Pocock's skills
alongside it either: pm-sp carries the parts it uses, and the rest of those
packs would pull sessions toward their own flows.

```
/plugin install pm-sp@dc-dev-plugins
```

## What's in it

pm-sp is the only plugin a pm-sp machine needs: **don't install Superpowers or
Matt Pocock's skills alongside it.** The parts of them it uses are copied in.

**The workflow (vendored Superpowers, v7.0.1, see [`VENDOR.md`](./VENDOR.md)):**
`brainstorming` (with the browser visual companion), `writing-plans`,
`subagent-driven-development`, `executing-plans`,
`finishing-a-development-branch`, `using-git-worktrees`,
`requesting-code-review`, `receiving-code-review`, `test-driven-development`,
`systematic-debugging`, `verification-before-completion`,
`dispatching-parallel-agents`. Without Superpowers' session-start hook, so
nothing takes over a session: skills fire when their description fits or when
named.

**Shaping foggy work (vendored Matt Pocock skills, see [`VENDOR.md`](./VENDOR.md)):**
`wayfinder` (decision tickets until the way is clear, ending in a set of
chunks), `grilling`, `domain-modeling`, `codebase-design`, `prototype`,
`research`, and `pr` for PR bodies.

**The session layer (pm-sp's own):**

- `whats-next`: session open. Reads design docs, plans and their ledgers,
  recent sessions; proposes the pick-up; writes the Intent.
- `stepping-away`: session close. Entry against the Intent, a resumable line
  per plan in flight, inbox capture, next-session offer.
- `checkpoint`: mid-session re-aim when the session can't break.
- `nested-sessions`: two or three plan lanes at once, each in a background
  session this one starts, steers and archives.
- `second-opinion`: Sol through Ringer plus a fresh Opus, on a design doc (as
  its builders) and
  on a finished branch.
- `ship-acceptance`: the design doc's Acceptance checks against the real
  candidate and production, recorded in `docs/shipped/`.

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
the workflow rules, `docs/` (inbox, quirks, a local tracker for
wayfinder; other folders appear on first write), `_pm/` with the skeleton and sessions. It runs the skeleton
interview. Also adds a stack's plugins to a repo (`stack vercel`).

## What it assumes

No other plugin. On the machine:

- **Ringer** and its library skills (`ringer`, `cross-review-gate`) on the Mac,
  for `second-opinion`'s Sol reader and `ui-test` (the marketplace README
  explains). Without them, second-opinion runs Opus alone and says so.
- **Python 3.9+** as `python3` on Claude Code's Bash PATH: the always-on
  credential guard and the session and delivery helpers need it (check with
  `python3 --version`). `ui-test` also needs Pillow (see `UI-TEST.md`).
- **Node**, for brainstorming's visual companion (a small local server).
- **git** with a remote, so wayfinder maps and plans travel between computers.

## Not carried over from pm

`discovery`, `fast-grill`, `orchestrate`, `session-succession`,
`verify-before-done`, `board`, `runway`. `WORKFLOW.md` says why for each.
Repos with `docs/intent/` files still work with `ship-acceptance`; new
projects put acceptance in the design doc.
