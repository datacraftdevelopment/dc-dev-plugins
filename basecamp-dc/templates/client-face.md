# Client face: Basecamp (basecamp-dc)

Installed once by the basecamp-dc plugin's `bc-setup` skill. This file is
yours after that: hand edits are preserved, setup never overwrites it. Ids
stay in `.basecamp/config.json` — never in this file.

## Where the close-out steps are

The installed **`bc-close-out`** skill (basecamp-dc plugin) — open it by name.
Conventions and voice live in **`bc-client-face`**; CLI syntax in the basecamp
CLI's own **`/basecamp`** skill. `bc-close-out` loads both before it writes.

## Evidence the steps consume

- The ticket file path — or the commit, when there is no ticket — for each
  item that moved this session.
- The ticket's `Client-ref:` line: the Basecamp Work item it maps to.
- In a repo that explicitly names a hand-kept `docs/TASKS.md` as
  its tracker, the `[bc:<id>]` token on the task line is the same join.

## What to do, case by case

| Case | Step |
|---|---|
| **Fully shipped** — every repo item behind the Work item is done | Run `bc-close-out` with the id from `Client-ref:` / `[bc:<id>]`, the ticket path or commit, and one plain-English sentence of what the client can now do. |
| **Partly shipped** — some items done, the rest open | `bc-close-out`'s partial path: the item stays in Active; post a `Status:` comment naming what is live. No move, no *What shipped* entry yet. |
| **Ticketless** — a change shipped from a session Intent with no ticket | Ask whether it belongs on the client face at all. If yes, name (or create, with approval) the Work item, then run `bc-close-out` with the commit as the evidence. If no, skip and say so. |
| **Missing mapping** — a shipped ticket with no `Client-ref:` and no `[bc:<id>]` | Never guess an id. Ask which Work item it belongs to; add the `Client-ref:` line to the ticket, then proceed as fully shipped — or record it skipped. |

## Authorization

Everything above writes to a client-visible project. A session close is
**not** authorization. An explicit request to perform the client update already
authorizes it; carry that authorization across turns without asking again.
Otherwise prepare the matching update and get approval before sending it.
Declining is a normal outcome.

## What counts as done

- **done** — `bc-close-out` finished and its own verification passed (a fresh
  `basecamp api get` shows the move, comment, and new Doc entry for a full
  close-out; for a partial close-out, it confirms the Status comment).
- **skipped** — the user declined, or nothing client-facing moved.
- **blocked** — missing config ids, a missing mapping nobody could resolve,
  or an unanswered question. Record exactly what is missing.

Record one of the three per item in the session entry.
