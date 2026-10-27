---
name: whats-next
description: Session open. Read where the work stands (specs, plans and their ledgers, what Runway is running and which hands-on tickets wait, in a Runway repo only; recent sessions), propose one or two things to pick up, and write this session's Intent. Use when the user says "what's next?", "what should I work on?", "where did we leave off?", "catch me up", or starts a session cold without a named task.
---

# What's next

The session open. Read first, then propose. Don't ask "what do you want to
work on?": that's what the user is asking you.

**If the user already named the work, there's no pick to make.** Read just
enough to write the Intent for it, write it, and start.

## 1. Read

The shared record first, the personal log second (`WORKFLOW.md`: `docs/` is
truth, `_pm/` is log).

First bring the record up to date: if the branch has an upstream and the
working tree is clean, `git pull --ff-only`, so a map, spec or plan moved
forward on another computer shows here. If the pull can't fast-forward, say so
and read what's local.

- **Plans in flight.** `docs/plans/*.md`, newest first. For each, find how far
  it got: its ledger at `.runway/sdd/<plan-name>/progress.md` when this
  checkout has one (it's gitignored, so another machine or worktree won't), and
  `git log` for the commits its tasks name. A plan with tasks left is a stream
  of work; the first unfinished task is its pick-up.
- **Specs not yet filed.** `docs/specs/*.md` with no tickets or plan from
  them: approved specs waiting for a go to file, or drafts waiting for
  approval.
- **Shipped records.** `docs/shipped/` tells you which designs were delivered
  (`ship-acceptance`); a `released-with-exceptions` record stays visible until
  the user accepts its open tail.
- **Waiting on the user.** Open questions in a spec, rulings in a ledger
  marked as needing the user, a second-opinion finding left open.
- **The inbox,** `docs/inbox.md` if the repo keeps one: loose ideas, one line
  each. A line is a candidate for shaping, not a task. Never a gate on
  starting work.
- `docs/adr/` newest entries and `GLOSSARY.md` if present.
- `_pm/skeleton.md`, the project's macro why.
- The last one to three files in `_pm/sessions/`, most recent first, especially
  their open threads and Intent vs. outcome.
- A map in `docs/maps/`, if the repo has one (`agent-runway:map`): its open
  decisions are decision work, not build work. Decisions carrying a
  `Waiting on:` line go under *Waiting on you*. A cleared map's chunks are
  spec candidates, in the order it set.
- **Runway,** only if `runway repo which` prints this repo's name (otherwise
  skip this item silently: no Runway mention, no ask):
  `runway status` and `runway hands-on`, each once, on its own line (the command on PATH, or the copy inside Runway.app). Its needs-you
  tickets go under *Waiting on you* with Runway's question as it gave it,
  never answered here. Hands-on tickets are this session's to pick up, with
  what waits on each. If Runway isn't on this machine, say so in a line
  and go on.

## 2. Propose

Keep work the session can take and decisions only the user can make apart.

```
Where we are: <one sentence: which designs and plans exist, how far each got>.
Ready to pick up: <a hands-on ticket, the first unfinished task of a plan, an approved spec to file, or "nothing in flight">.
Waiting on you: <a spec to approve, a go to file, Runway's questions, open questions, or "nothing">.
Recommended: <one pick-up> because <reason from what you read>.
Also worth: <maybe one more>.
Watch-outs: <a plan with no commits in a while, a ledger and git that disagree, an unseated review>.
```

New work with nothing shaped yet goes to `agent-runway:grill` (and
`agent-runway:prototype` when seeing beats talking, `design-handoff` for
screens), ending in `agent-runway:spec`. Work that is genuinely foggy, with
several unknowns that depend on each other, gets `agent-runway:map`: suggest
it, don't start it; its destination is a set of chunks, a spec each.

## 3. Write the Intent, when there is one

Two or three sentences of plain prose: what this session pushes on, why it
matters, what done-for-this-session looks like, what's out of scope. Scope it
to one session. Once the pick is settled (a named task counts), open the
session record:

```bash
ROOT="$(git rev-parse --show-toplevel)"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/session.py" --root "$ROOT" open --name <handle> --intent '<session intent>'
```

When the session starts fuzzy (thinking out loud, exploring, not sure yet
what to pick), open it without `--intent` and don't make one up to fill the
slot. The file says the Intent isn't set. Once the work firms up, set it
with a re-aim (the `checkpoint` command), which becomes the session's aim.
Some sessions never firm up, and that's fine.

Keep the absolute `ROOT` with the returned `path` and `id` (pm-sp): the plan
may move this session into a worktree, and close and re-aim must still find
the same file. Keep all three in this conversation and in any handoff
summary; they bind this conversation to this session. Never pick a session file
by its ordinal. On resume, reread that file's Intent and latest re-aim.

## 4. Work

Shaped work is done here, with the user in the loop. In a repo that isn't in
Runway, that is the whole story: no tickets, no Runway suggestions, no asking.
In a Runway repo, the agent-runway skills ask once, after the spec is shaped
and only when the work is a good fit (several independent, checkable pieces;
not mostly device or by-eye work), "Run this through the Runway app, or do it
here?", and keep the answer in the spec's front matter (`runway: yes|no`).
`yes` goes to `agent-runway:file-tickets`; `no`, or a poor fit that is never
asked about, goes hands-on here via `agent-runway:hands-on`:
a plan when it's more than a step or two, run by
`agent-runway:subagent-driven-development` or `agent-runway:executing-plans`,
then, for a Runway hands-on ticket, `runway done` on the user's go. A quick, fully specified task is just
done, test-first.

## No history yet

A brand-new project: offer to draft the skeleton if it is still a placeholder,
or to shape the first piece of work. The Intent is then "draft the
skeleton" or "shape the first piece".
