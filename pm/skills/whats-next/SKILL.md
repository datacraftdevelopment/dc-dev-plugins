---
name: whats-next
description: Session open — propose 1-2 things to pick up AND draft this session's Intent block (the agent's anchor while it works). Use when the user says "what's next?", "what should I work on?", "where did we leave off?", "catch me up," or starts a session cold without a specific task in mind.
---

# What's Next

Session open. The user is starting a session — could be the second one today after closing a full thread, future-them four days later, or a teammate cold-starting. Ground the answer in context, not vibes, and **draft an Intent block** they can paste into this session's entry to keep the agent oriented during execution.

**Don't ask "what do you want to work on?"** That's what they're asking *you*. Read first, then propose.

**If the user already named the work, there is no selection to make.** Skip the proposal round: read enough context to draft the Intent block for the named work, write it, and start. Don't re-open the pick, don't run the full survey below, and don't ask for approval the naming already gave.

**Succession handoff:** when the startup prompt names a chain and launch attempt,
read [session-succession](../session-succession/SKILL.md) first. Revalidate its
named ticket and authorization, then allocate this session's own Intent/binding
without another selection round. Acknowledge the handoff and wait for retirement;
only `begin` authorizes taking checkout ownership and dispatching subagents. This
overrides "write it, and start" above for successors. Ordinary session opens retain
the checklist below. A handoff is a compact brief, not a transcript to reload.

## Checklist

**1. Read.** Shared record first, personal log second (`WORKFLOW.md`: `docs/` is truth, `_pm/` is log).
- `docs/intent/*.md` — every open intent (status draft/accepted and no verified Completion link; `ship-acceptance` owns completion): these are the streams of work. Note each one's size call.
- For a Completion link, read the linked delivery record before excluding a `shipped` intent. Surface `released-with-exceptions` with its open tail until the originator accepts it; a missing/broken record stays open.
- **The tracker** — the frontier: open wayfinder tickets (unblocked, unclaimed) and open implementation tickets. GitHub: `gh issue list --label wayfinder:map`, then children; local: `.scratch/<name>/` per `docs/agents/issue-tracker.md`. Unreachable → say so, go on with local artifacts. **Waiting tickets** — any ticket carrying `Waiting on:` (and `Status: needs-human`) — are not frontier: list them under *Waiting on you* with who and since when, never as the pick-up.
- **`docs/intent/inbox.md`** — the ungroomed list: loose asks and ideas that have not been shaped. Read it after intents and the frontier. A line here is a discovery candidate, not a task. **Grooming is optional, never a gate on starting work:** if the file holds more than twelve lines, or any line is dated before the last four session files, note that in the proposal and *offer* a keep / promote (→ `discovery`) / merge (into an existing intent or ticket) / retire pass — a retired line is deleted from the file and the reason goes in this session's entry. The user can decline or defer; proceed to the pick-up either way. Otherwise say nothing about age.
- `docs/adr/` newest entries, `GLOSSARY.md` (or `CONTEXT.md` in older repos) if present — what's been decided.
- `_pm/skeleton.md` — the macro why of the project.
- Last 1–3 session files in `_pm/sessions/` (any author, most recent first) — especially Open threads and the previous session's Intent-vs-outcome. The immediately preceding session may be earlier the same day; read it as the live handoff.
- `knowledge/index.md` — only if a knowledge bundle exists. Skim; don't crawl.
- **A hand-kept task file** (`_pm/TASKS.md`, `docs/TASKS.md`): if the repo's `CLAUDE.md` names it as the tracker of record, treat its Current and Next sections as the frontier — that repo decided so. Otherwise it is legacy: read it as a hint only, don't grow it, and point at `MIGRATION-0.17.md` for the retirement rubric. A file whose first line says `> Legacy` is skipped entirely.

**2. Propose.** Output:

Keep **actionable work** and **decisions waiting on the user** as separate lists — a ticket the agent can take next is not the same thing as a question only the user can answer, and mixing them buries both.

```
Where we are: <one sentence — which streams exist and what stage each is at>.
Frontier (actionable): <takeable tickets, or "nothing charted yet">.
Waiting on you: <decisions only the user can make — seat splits, doors, waiting tickets
  with who and since when, a draft intent needing acceptance; or "nothing">.
Ungroomed: <inbox lines, or "inbox empty"; stale/excess lines offered for keep / promote / merge / retire>.
Recommended pick-up: <one specific ticket / next stage step / "discover <inbox line>"> — because <reason tied to context>.
Also worth: <maybe one more>.
Watch-outs: <claimed tickets gone quiet; open threads worth surfacing>.
```

**3. Draft the Intent block** for the most likely pick-up. Two or three sentences of plain prose — what we're pushing on, why it matters, what done-for-this-session looks like, anything explicitly not in scope. Scope it to one session's worth of work, not a whole day's. Example:

> Pushing on the search filter UI — Sandy's manual workaround is costing her ~20 min/day, and a working filter unlocks the rest of the search flow. Done for this session is the prototype validated by Sandy. Not touching filter persistence or multi-category yet.

**4. Resolve the pick-up.** Named work or existing authorization to continue the
ready work within a settled scope is the selection: proceed without another
approval round. Otherwise present the recommendation and wait for the user's
selection. A missing outcome or permission is a real question; choosing the next
ready item in an already authorized scope is routine orchestration.

**5. Write.** Once the selection is settled (named work counts as settled; an accepted `dc-autonomy-v1` Execution agreement covering this scope authorizes the session-file write itself as local bookkeeping), write the Intent block into this session's file in `_pm/sessions/`:

Use the bundled allocator after the user has selected the work (an explicit task already states the selection):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/session.py" --root . open --name <handle> --intent '<session intent>'
```

Keep the returned `path` and `id` in this conversation and its handoff/compaction summary. They bind this conversation to this session; never select a newer file by ordinal. The allocator creates the next readable date/person filename with exclusive creation and adds `Session-ID` and `Started`. Local concurrent allocations cannot overwrite each other. Offline replicas of a synced folder do not share a lock: use separate project checkouts for simultaneous work across machines and preserve conflicting files for reconciliation.

On resume/context recovery, read that file's opening Intent and latest Re-aimed section, then reconcile with the tracker and shared docs. If the binding was lost and more than one file could belong to this conversation, ask once. Legacy files without an ID remain readable; do not adopt one merely because it is newest. An explicit session path supplied by the user can be continued manually with the same append-only rules.

If the stream's wayfinder ticket is what's being picked up, **claim it on the tracker** (assign to self) — the assignee is the claim. For a succession handoff, confirm the chain's existing reservation and transfer it only after `begin`; do not create a competing claim.

**6. Execute.** Do the work in this session, one outcome at a time, with the
user in the loop. That is the default. Reach for
[orchestrate](../orchestrate/SKILL.md) only when the user asks for it, or when
there is a real batch of independent tickets, each worth an hour or more, and
the user will be away; say so and let them choose. Two or three ready tickets
that are independent of each other go to sibling sessions first: use the
[sibling-sessions](../sibling-sessions/SKILL.md) skill, which decides whether it
is appropriate, launches them and then leaves them alone. When orchestrating, worker
briefs belong under the existing outcome ticket; do not generate a ticket
for each little task. Keep human questions on the tracker and surface them
together in this conversation. A successor reaches this step only after `begin`.

## When the project has no history

Brand-new project: propose drafting the skeleton (if still placeholder), or running `discovery` on the first piece of work so there's an intent to stand on. Still draft an Intent block — the push this session IS "draft the skeleton" or "discover the first stream."

## Why this skill matters

> "These systems were built to execute. They nail the *what* and quietly let the *why* go." — Matt Maher

The Intent block is this session's why. Reread it at resume/context recovery, before another ticket or manually controlled wave, and at checkpoint. Without it, the agent has the queue but no orientation.
