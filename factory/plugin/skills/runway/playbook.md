# Playbook: Matt Pocock's skills with Runway

How a repo runs when the thinking happens in sessions with Matt Pocock's skills
and the building happens in Runway. Bring this file into a new repo and tell the
session: "Read the Runway playbook and set this repo up for it." It lives in the
factory plugin at `skills/runway/playbook.md`, so any session with the plugin
installed can read it at `${CLAUDE_PLUGIN_ROOT}/skills/runway/playbook.md`.

The runway skill and the repo's `docs/agents/issue-tracker.md` hold the full
rules. This file is the order things happen in, and the places where Matt's
defaults and Runway's disagree.

## The split

Sessions decide, Runway builds.

| Stage | Who does it | Output |
|---|---|---|
| Shape the idea (optional) | You, in a session, with pm's `discovery` | `docs/intent/<slug>.md` |
| Find the way | You, in sessions, with `/wayfinder` | A map issue and its decision tickets, all resolved |
| Write the destination down | A session, with `/to-spec` | `docs/specs/<slug>.md` on main, plus a `spec` issue |
| Cut the work | A session, with `/to-tickets` | Build tickets as sub-issues of the spec, each with one gate label |
| Build | Runway, unattended on the Mac | Commits on `runway/integration`, one ticket at a time |
| Decide | You, by answering decision packets | A `go` (or `drop`) comment on each `ready-for-human` ticket |
| Review and hand over | Runway's finish step | A reviewed branch and a draft PR |
| Merge | You | `main` |

Runway never touches `main`, and never reads anything Wayfinder makes. The
hand-off between the two halves is the spec and its labelled tickets.

## What the machine needs

On the Mac that runs the loop, once:

- The `factory` and `pm` plugins from this marketplace
  (`/plugin install factory@dc-dev-plugins`, `/plugin install pm@dc-dev-plugins`).
- Matt Pocock's skills. Version 1.3 renamed `CONTEXT.md` to `GLOSSARY.md`; use
  whichever name the installed version writes, and don't keep both.
- `gh` signed in (`gh auth status`) for a GitHub repo, or the Linear key in the
  keychain (service `runway-linear`) for a Linear project.
- `claude` signed in. Ringer is optional: with it the finish review is a
  two-seat panel, without it a single Claude review.

## Set up a new repo

Steps marked **(you)** need your hands or your say-so; a session does the rest.

1. **Pick the tracker.** GitHub Issues on the repo itself, or a Linear project.
   One tracker per repo. If the repo is public, every issue and every Runway
   comment is public too: no client names, credentials or NDA material.
2. **Matt's setup, if you want it (you).** `/setup-matt-pocock-skills` is
   interactive and only you can start it. Run it *before* step 3. If it ever
   runs after, re-run step 3, because Matt's setup rewrites
   `docs/agents/issue-tracker.md` and drops Runway's gating rule.
3. **Point the repo at the tracker.**
   - GitHub: `bash "${CLAUDE_PLUGIN_ROOT}/runway/setup.sh" <repo> --github [owner/name]`
   - Linear: `bash "${CLAUDE_PLUGIN_ROOT}/runway/setup.sh" <repo> <TEAM-KEY> "<project name>"`

   It writes `docs/agents/issue-tracker.md` (labels, gating rule, conflict
   screen, Wayfinder's operations), seeds `triage-labels.md` and `domain.md`
   when missing, writes `runway.json`, adds an "Agent skills" section to
   `CLAUDE.md`, and commits.
4. **Labels.** `python3 "${CLAUDE_PLUGIN_ROOT}/runway/runway.py" --root <repo> setup`
   checks the sign-in and the repo or project, then creates Runway's labels
   (`go`, `needs-human`, `spec`) and, on GitHub, Matt's five triage labels. It
   never recolors a label that already exists. Wayfinder's labels
   (`wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`,
   `wayfinder:grilling`, `wayfinder:task`) aren't Runway's; create them with
   `gh label create` the first time a map needs them.
5. **Edit `runway.json` before the first run.** The template assumes a Python
   repo, so:
   - `check_cmd`: the repo's real test command, run from the repo root in a
     fresh worktree. It must install what it needs (`npm ci && npm test`, a
     `bash scripts/check.sh` wrapper, and so on).
   - `agent_cmd` `--allowedTools` (and the same key in the `opus` harness):
     allow whatever the worker needs to build and test here. The template allows
     only `python3 -m unittest`, `python3 -m pytest` and a few `git` commands, so
     a Node repo needs `Bash(npm:*)` and `Bash(node:*)` or the worker can't run
     its own tests.
   - `"spec": "<path or #issue>"`: optional. When set, the finish review judges
     the whole branch against it.
   - `"finish"`: `all_done` (default) waits until no ticket is open, so a parked
     decision holds the PR; `idle` finishes whenever nothing can run; `off`
     never finishes on its own.
   - `"pr"`: `file` (default) writes the PR body to `_pm/runway-pr.md`;
     `draft` pushes `runway/integration` and opens or updates a draft PR.
   - `"review"`: `panel` (template) or `single`.
6. **Worker environment.** Copy `${CLAUDE_PLUGIN_ROOT}/runway/worker-env.md` to
   `docs/agents/worker-env.md` and fill it in: what a fresh worktree lacks
   (env files, dependencies, local data), the verify command, and paths a ticket
   must leave alone. Every ticket run reads it first. Commit it.
7. **Commit and push to main.** The engine reads `runway.json` and the docs from
   your local checkout and never fetches, so pull on the Mac after any change
   made elsewhere.
8. **Schedule it (you), once the first tickets are labelled.**
   `bash "${CLAUDE_PLUGIN_ROOT}/runway/schedule.sh" install <repo> [minutes]`
   loads a LaunchAgent that runs the loop every 10 minutes by default. It runs on
   your Mac, so it needs your say-so.

## The chain, step by step

### 1. Discovery (optional)

pm's `discovery` skill riffs the problem into `docs/intent/<slug>.md`: problem,
outcome, who's affected, what's fixed, what's open. A written intent makes
Wayfinder's opening grill much shorter. Skip it when you already know the shape.

### 2. Wayfinder

`/wayfinder` turns a destination too big for one session into a **map**: one
issue labelled `wayfinder:map`, with child decision tickets labelled
`wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling` or
`wayfinder:task`. You resolve them one session at a time.

- **Grilling** tickets call Matt's `grilling` and `domain-modeling`. To spend
  fewer of your answers on technical questions, use pm's `fast-grill`:
  technical questions go to a second model through Ringer, and only taste,
  one-way doors and splits come to you.
- **Prototype** tickets call `/prototype` for something rough to react to.
- **Research** tickets run as background agents and leave findings on a
  throwaway `research/<name>` branch.
- **Task** tickets are manual work a decision waits on (sign up for a service,
  provision access).

Runway ignores all of this, and that's what you want. It only loads issues with
its own labels, and a map has sub-issues, which Runway reads as a spec it never
runs. Two rules keep it that way:

- **Never put `ready-for-agent` or `ready-for-human` on a map or its children.**
  They're decisions, not build work.
- **Wayfinder claims a ticket by assigning it to you**, and Runway reads any
  assignee as "claimed". Another reason the two sets of tickets must stay apart.

The map is done when no tickets remain and the way to the destination is clear.

### 3. `/to-spec`

The spec is a **file in the repo**: `docs/specs/<slug>.md`, on `main` before any
of its tickets is labelled for Runway, so every worker reads it from its own
checkout. Then publish the tracker entry: an issue whose first line is
`Spec: docs/specs/<slug>.md`, followed by a copy of the text. A later change
goes into the file first, then gets re-pasted into the issue.

Label the spec issue `spec`. **Never** `ready-for-agent` or `ready-for-human`,
whatever Matt's skill says: `/to-spec` applies `ready-for-agent` by default, and
Runway would otherwise try to build the spec.

> The spec-file half of this step depends on PR #58 ("Specs live in the repo").
> Until it is on main, the spec lives only in its issue, and the worker reads it
> through `gh issue view`, so `Bash(gh issue view:*)` must be in `agent_cmd`'s
> `--allowedTools`. Without it a headless worker can't reach the spec and the
> ticket parks.

### 4. `/to-tickets`

Publish the build tickets as **sub-issues of the spec issue** (on Linear, child
issues), in the order they should land, each with **exactly one** gate label
from the table below. `/to-tickets` applies `ready-for-agent` to everything by
default; sort each ticket before you accept that.

### 5. Runway

Each tick, Runway:

- posts a decision packet on every unblocked `ready-for-human` ticket and adds
  `needs-human`;
- runs the next unblocked `ready-for-agent` ticket headless in its own worktree,
  test-first (`/tdd`), checks it with `check_cmd`, and merges it into
  `runway/integration`. A failed attempt gets one retry; after that, or when the
  worker writes a question instead of finishing, the ticket parks as
  `needs-human`.

When the queue is done (per `"finish"`), it reviews the whole branch, makes one
fix pass, re-runs the check, and writes the PR body or opens the draft PR.

### 6. You

Answer decision packets, then review and merge the PR.

## Labels on build tickets

Sort each ticket into the first row that fits.

| The ticket is… | Label | What Runway does |
|---|---|---|
| A one-way door: live or client data, deletes, anything public or production, spend, credentials, an architecture choice that takes more than a session to undo | `ready-for-human` | Posts a decision packet, adds `needs-human`, and builds once you say `go` |
| A plan that contradicts something you said | `ready-for-human`, quoting you | Same |
| Taste: anything a user sees or feels, or what "done enough" means | `ready-for-human` | Same |
| Technical: anything the code or the spec can settle (file layout, a library inside the chosen stack, naming, test seams, endpoint shape) | `ready-for-agent` | Builds it unattended |
| Work only you can do (accounts, secrets, signing, pricing, branding) | **No Runway label.** A plain label of your own is fine | Never runs it, but it **still gates** any ticket that lists it as a blocker |
| Needs architecture judgment (add to one of the above) | `harness:opus` | Runs on Opus instead of the default Sonnet |

- Unsure between taste and technical: `ready-for-agent`, with the assumption
  written in the body so the finish review can catch it.
- Unsure whether it's reversible: it's a door.
- Never both gate labels on one ticket. `needs-human` and `go` are Runway's to
  set and clear; don't touch them by hand.
- Work under about an hour isn't its own ticket. Fold it into the ticket it
  serves.

Runway's `ready-for-human` means "you decide, then an agent builds". In Matt's
vocabulary it means "a human implements this". Work you'll do yourself stays
unlabelled.

## Ticket body

```
Blocked by: #12, #14
Spec: docs/specs/<slug>.md

## What
One outcome, under the spec.

## Acceptance
- Observable checks, each naming the command that proves it.

## Scope
Files and folders it may touch. Paths to leave alone.

## Assumption
(ready-for-agent, only when taste vs technical was unclear) The call the agent
should make, so the finish review can catch it.

## Why you
(ready-for-human only) The decision needed, and what "go" will make the agent do.
```

- `Blocked by:` is only needed when native dependencies aren't used (GitHub's
  "blocked by", Linear's blocks relation). When present it must be the first
  line of the body.
- `Spec:` sits under `Blocked by:` (PR #58).
- Without sub-issues, put `Part of #<spec>` at the top instead.

## Order and collisions

- Runway takes unblocked tickets oldest first (by issue number on GitHub), so
  publish them in the order they should land.
- **Conflict screen.** Two tickets that touch the same files (lockfiles,
  generated code, migrations, schema and config registries), write the same
  database, or need the same port must not run side by side. Give them a
  "blocked by" edge in landing order, even when neither needs the other's
  output.
- Anything that needs a desktop app open, or writes a real data file rather
  than a scratch copy of a fixture, is a door. Headless workers can't drive a
  GUI.
- In a monorepo, Runway takes every gate-labelled issue in the repo, not only
  the ones for the part you're working on.

## Answering decisions

A decision packet is a comment starting `🛫 runway`. Reply with a comment
starting `go`, and whatever follows reaches the agent (`go option B, keep the
old endpoint`), or `drop` to close the ticket as not planned. The `go` label
works too. On GitHub only a comment from the repo's owner, a member or a
collaborator counts.

A session can post the `go` for you, but only after you've said go on that
specific ticket, with your choice. `gh` and the Linear connector write as you,
so Runway can't tell a session's go from yours.

To see what's waiting: `RUNWAY status --json` (the `waiting` group), or
`gh issue list --label needs-human`.

## Gotchas

- **Matt's defaults label too eagerly.** `/to-spec` and `/to-tickets` both
  apply `ready-for-agent`. The spec gets `spec`, and every ticket gets sorted.
- **Matt's setup overwrites Runway's tracker doc.** Re-run `setup.sh` after it.
- **Map tickets and build tickets never mix.** Wayfinder's assignee claim and
  Runway's claim use the same field.
- **Workers only have what `agent_cmd` allows.** A worker that can't run the
  test command can't pass `check_cmd` either; it retries once and parks. Widen
  the allowlist in `runway.json`, never per ticket.
- **The engine reads the local checkout.** Pull on the Mac after changing
  `runway.json`, `worker-env.md` or a spec elsewhere.
- **Closing a chat doesn't stop the loop.** Pause it (`RUNWAY pause --for 1h`)
  or remove it (`schedule.sh uninstall <repo>`).

## Ready-to-run check

Before you turn on the schedule, a session can confirm:

- [ ] `runway.json` exists, with the right tracker, a real `check_cmd`, and an
      `agent_cmd` allowlist that can run it.
- [ ] `docs/agents/issue-tracker.md` has Runway's gating rule (re-run `setup.sh`
      if Matt's setup replaced it).
- [ ] `docs/agents/worker-env.md` is filled in.
- [ ] `RUNWAY setup` passes and the labels exist.
- [ ] The spec is on main (`docs/specs/<slug>.md`) and its issue is labelled
      `spec` only.
- [ ] Each build ticket is a sub-issue of the spec with exactly one gate label,
      and the conflict screen is applied.
- [ ] `RUNWAY status --json` shows the tickets you expect in `ready_auto` and
      `ready_prep`, and nothing from the Wayfinder map.

Here `RUNWAY` means `python3 "${CLAUDE_PLUGIN_ROOT}/runway/runway.py" --root <repo>`.
