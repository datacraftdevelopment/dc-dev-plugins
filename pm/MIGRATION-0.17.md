# Migrating a project to pm 0.17

pm 0.17 stands the tracker up by default and gives loose asks a home. Three
files are new in scaffolded projects; existing projects add them by hand or
with `/pm:pm-scaffold here` (which writes them only if absent).

| File | What it is |
|---|---|
| `docs/agents/issue-tracker.md` | Local markdown tracker under `.scratch/`, Matt Pocock's convention, preset. Re-run `/setup-matt-pocock-skills` to choose GitHub Issues instead. |
| `docs/intent/inbox.md` | Loose asks and ideas, one line each, no status. The tier below an intent. |
| `docs/agents/client-face.md` | Optional. Names a client-facing tracker and its close-out procedure; `stepping-away` follows it if present. See the pm `stepping-away` skill's `client-face-contract.md`. |

## The three tiers

```
docs/intent/inbox.md      loose: one line per ask or idea, dated, sourced. No status.
docs/intent/<slug>.md     shaped: discovery ran, size call made.
.scratch/<slug>/issues/   the tracker: implementation tickets, and question tickets
                          whose answer is the work. Never a loose idea.
```

An item only moves down. Waiting is a tracker state: `Waiting on:` plus
`Status: needs-human`, restored by hand when the last answer lands.

## Retiring a `TASKS.md` (pm ≤ 0.7 layout, or any hand-kept task file)

Triage every item, one row each, into the session entry. Each row names a
destination path that exists, or a dated reason.

| Item is | Goes to | Row says |
|---|---|---|
| Shipped, moot, or overtaken | nowhere | `dead · <date> · <evidence: commit, changelog line, or "confirmed with Joe">` |
| A loose idea or a someday ask | `docs/intent/inbox.md` | the inbox line, verbatim |
| Work with a shape but no plan | `docs/intent/<slug>.md` (run `discovery`, or a short retroactive intent) | the intent path |
| Work with a known shape | `.scratch/<effort>/issues/NN-<slug>.md` | the ticket path |
| Conditional or operational ("rotate X if live") | a ticket with `Waiting on:` and `Status: needs-human`, or an inbox line naming the condition | the path; **unknown completion stays live**, never `dead` |

Then put `> Legacy — not maintained since <date>; retired per pm MIGRATION-0.17`
as the file's first line, or delete it. The session rituals stop reading it.
A cold `whats-next` in the next session must surface every surviving item from
the new files without opening the old one; if it can't, a row is wrong.

## A repo that decided `TASKS.md` *is* its tracker

Some repos (RCC_SB-SOS, decided 2026-08-26 under pm 0.9) run a hand-kept task
file as their tracker of record, with a working meeting → batch → client-face
loop on top of it. That stays legitimate. pm reads such a repo as follows:
`whats-next` treats the file as the tracker frontier (its Current and Next
sections), not as a legacy hint; `stepping-away` settles it the way it would
settle any tracker the user owns. Migrating is that repo's call, made from
inside it after reviewing what 0.17 buys. The rubric above applies if it does.

## Skill changes to know about

- `whats-next` reads the inbox after intents and the frontier, lists waiting
  tickets under watch-outs, and asks about stale or excess inbox lines.
- `discovery` removes the inbox line it shaped and cites it in Source.
- `stepping-away` matches an ask against inbox, intents, and tickets before
  adding a line; retires inbox lines by deleting them with the reason in the
  session entry; follows `docs/agents/client-face.md` if present.
