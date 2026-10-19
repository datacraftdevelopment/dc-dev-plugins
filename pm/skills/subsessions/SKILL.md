---
name: subsessions
description: Run two or three independent ready tickets at once, each in its own subsession that this main session starts, steers, follows up and archives, so the user talks to one session instead of going into each one. Use when the user says "subsessions", "spin up a subsession", "sibling sessions", "implement sibling sessions if appropriate", "run these in parallel sessions", "open another session for that ticket", "you manage the sessions", or when ready tickets look independent and the user wants them moving at once. This is the default way to parallelize, ahead of orchestrate's subagents. NOT a succession chain (session-succession) and NOT unattended Ringer workers (orchestrate, build-swarm).
---

# Subsessions

Two or three subsessions running side by side, each an ordinary session on its
own ticket, worktree and branch. This session is their **main session**: it
starts them, answers or relays their questions, follows up when one goes quiet,
lands their work by the merge rule and archives them when they are done. The
user talks to the main session. They can open a subsession, but they never have
to.

Why the main session manages them now: subsessions report back on their own.
A subsession's message wakes the main session, so managing them costs a turn
per event, not a session kept alive polling. Polling was the expensive part of
the old lane orchestrator (pm-018, pm-021), and the reason `sibling-sessions`
left its siblings unwatched. That reason is gone where the host has subsession
messaging; it still holds where it doesn't (see §6).

## 1. Decide whether it is appropriate

"If appropriate" is a real question. Answer it out loud, yes or no, with the reason.

Say **yes** only when all of these hold:

- There are at least two ready tickets, each a meaningful outcome. Small fixes
  stay in this session, done serially.
- **Disjoint files.** List what each ticket will touch. Any overlap, including
  lockfiles, generated code, migrations, schema or config registries, means
  those two run one after the other.
- **At most one database writer**, and no shared port, dev server, browser
  profile or other single resource.
- No ticket depends on another's output. A dependency is a second wave, started
  when the first merges.
- The machine has room. Check memory and CPU (`memory_pressure`, `uptime` on
  macOS). Three sessions building at once ran a 16 GB Mac out of memory.
  Subsessions in the cloud don't load the user's machine; say which you use.

Otherwise say **no** and name the alternative: do them serially here, or, for a
real batch of check-judged tickets while the user is away, `orchestrate`.

**Three subsessions at once is the ceiling.** The main session counts as one
when it is building too; when it only manages, three subsessions plus it.

## 2. Start each subsession

One subsession per ticket, through the host's session tools (spawn, message,
list, stop or archive; the names vary by host, so use whatever this host
lists). Give it a short self-contained brief that points at things rather than
copying them:

```
Repo: <checkout path>. You are a subsession of <main session name>; the other
subsessions are working <ticket ids>, leave those alone.
Run whats-next bound to ticket <id>: <title>. Do not pick other work.
Work in your own worktree on branch <name>. Set it up from
docs/agents/worker-env.md if the repo has one.
Report to the main session, not the user: a short message when you are blocked,
when you have a question, and when the ticket is green and ready to merge
(branch, head commit, what the checks proved). The main session will send you
review findings to fix. Do not wait on or message the other subsessions.
Merge only when the main session says so. Close with stepping-away.
Handoff: <this session's file>.
```

Name the ticket so two subsessions never pick the same one; the subsession's
own `whats-next` claims it. A fresh worktree lacks uncommitted work and
everything git ignores (env files, dependencies, local databases, `_pm/` where
it is ignored), so commit what the subsession needs first and say in the brief
what it has to set up. Where `_pm/` is ignored, tell it to write its session
file in the main checkout.

Ask the host to tell you when each subsession goes idle, if it offers that.
Report each one as **created and pending** until it has actually started, then
give the user one line per subsession: ticket, branch, where it runs.

## 3. Manage them

Act on events, not on a timer. Each turn a subsession wakes you:

- **A question.** Answer it yourself when the repo, the ticket, the spec or an
  earlier decision answers it, and say where the answer came from. Bring the
  user only a real decision (taste, scope, anything hard to undo), one line
  with your recommendation, naming the subsession. Relay their answer back.
- **Blocked.** Unblock it (commit a missing file, settle an interface, reorder
  the waves) or park its ticket with `Waiting on:` and tell the user once.
- **Green.** Before anything merges, get an adversary review of the
  subsession's diff from a different model, through Ringer (the
  `cross-review-gate` skill on the Codex seat). The reviewer reads the diff,
  the ticket and the check output, nothing else. Send its findings to the same
  subsession to fix; it keeps its context, so the fix is not a cold start.
  After the fix, review once more. A second failed review parks the ticket
  with `Waiting on:` and its findings, the same rule Runway uses. Don't review
  inside a Claude subsession: the point is a second model's eyes.
- **Ready to merge** (review passed). Read its report and diff by path. The first ready merges
  first; later ones rebase onto it, and a conflict is that subsession's to
  resolve. Merge on the user's word, or under a merge rule the user gave
  earlier in this session. Push, deploy and client messages keep their own
  authorization.
- **Gone quiet.** If a subsession has been idle without reporting, message it
  once asking for status. Read its transcript only if it doesn't answer.

Steer by message, short and pointed: a changed decision, a new constraint, a
file to read. Don't restate the brief. Don't read subsession transcripts on
every turn; their reports are what you keep in context.

The main session owns the shared things: the tracker's ordering, the
changelog, the client face, the integration branch. Subsessions don't edit them.

## 4. Archive

When a subsession's ticket is merged and its `stepping-away` has run, check its
worktree is clean and its branch merged (`git merge-base --is-ancestor`), remove
the worktree, and archive or stop the subsession through the host's control.
Archive a subsession whose ticket was dropped or parked too, once its state is
written on the ticket. Never leave one running with nothing to do.

When the last one is archived, tell the user in one message: what merged (with
commits), what each check proved, what is parked and on what.

## 5. What each subsession does

The normal loop, reporting to the main session:

1. `whats-next` bound to the named ticket.
2. The work, in its worktree, committing at green checkpoints so a crash costs
   reasoning, not work.
3. Rebase on the base branch, run the project's checks on the rebased tree,
   and report to the main session.
4. Fix what the adversary review finds, re-run the checks, report again.
5. Merge when the main session says so.
6. `stepping-away`. The main session removes its worktree and archives it.

## 6. Hosts without subsession messaging

If this host can open sessions but they can't message back (a click-to-start
chip, a plain new window), fall back to unmanaged siblings: each one is told to
report to the **user**, own its ticket through its own merge on the user's word,
and close itself. The main session then lets go: no polling, no transcript
reads, no integration. If the user asks how one is doing, look once and answer.
No session-creation control at all: print the briefs for the user to paste.

## Next to implement-spec

A whole spec already cut into tickets is Matt Pocock's `implement-spec`: it
walks the ticket graph with background implementer subagents and a merger.
Use it when the user asks for it. This skill is for two or three tickets the
user wants moving at once, each needing a session of its own.

## What this skill does not do

- No lane board and no polling loop.
- No unattended work. A ticket a check can fully judge, with the user away, is
  `orchestrate` or `build-swarm` territory.
- No chain. One subsession per ticket; `session-succession` is a different thing.
- No more than three at once.
