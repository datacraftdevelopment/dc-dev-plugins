# Spec: runway-db, a third tracker adapter

Talked through with Joe on 2026-10-14. Tracker entry: the `spec` issue that links here.

## Problem

Runway's queue lives in GitHub Issues or Linear. Neither is a database, so the protocol works around them: claims
between Macs are settled with comment stamps and a lease, a park can land half done and needs a local journal and one
designated Mac, and Joe's go is found by paging comments. Joe also wants one place, across every project and every
machine, that holds the queue and what waits on him.

## Direction

A hosted Postgres database (Supabase), built in its own **private** repo, `runway-db`. Runway reaches it through a
third tracker adapter that sits behind the existing ticket protocol, exactly like GitHub and Linear. GitHub and
Linear keep working unchanged; a repo opts in with `"tracker": "runway-db"`.

This spec covers only the Runway side: the adapter and the contract it needs from the database. The schema, the
page and everything about how projects are organized live in the private repo.

**Loop first** (Joe): the first goal is a Runway loop on a practice repo that claims, builds and closes tickets held in
the database. Nothing else (page, imports, MCP, moving this repo over) until that has run for real.

## The adapter

`pm/runway/runway_db_tracker.py`, stdlib only, talking to Supabase's REST API (PostgREST) over HTTPS.
`tracker_class` in `runway.py` learns `"runway-db"`, and the engine's README lists it beside `github` and `linear`.

**Config** (`runway.json`):

```json
"tracker": "runway-db",
"runway_db": {
  "url": "https://<project-ref>.supabase.co",
  "project": "RW",
  "park_authority": ""
}
```

**Key:** `RUNWAY_DB_KEY`, or the macOS keychain item `runway-db` (same pattern as `runway-linear`). Never in
`runway.json`, never in git. The tracker's `signins` check reports a missing key without touching the network.

**Rules:** a new `ticket_protocol.Rules` entry: name `runway-db`, children "child tickets", where "in runway-db",
every comment trusted (only keyed writers can post, as with Linear's private workspace), close then comment
(`close_with_comment=False`), so the protocol's existing two-write order applies.

**Facts** (from the contract below): id `RW-42`, num `42`, title, body, url (empty until the page exists), labels,
latest 50 comments plus older pages through `_older_comments`, closed, held (`held_by` set), has children (any
ticket with this one as parent), blocked by (from `ticket_blocks`), and the parent spec as `parent_issue`.

**Writes:**
- `_post`: insert a comment.
- `_claim`: one conditional update, `held_by = <machine>` where `held_by is null and state = 'open'`, asking for the
  row back. No row back means another runner won, and the adapter raises the same error a failed GitHub claim does.
  This is the one new guarantee; the protocol's stamp and lease still run on top and stay harmless.
- `_close(reason, full)`: set `state = 'closed'`, `close_reason`, clear `held_by`; post `full` if given.
- `_release(add, remove)`: clear `held_by`, change labels, in one update.
- `_relabel(add, remove)`: change labels.
- `create(title, body, labels)`: insert into the configured project; the database assigns the number.

Timeouts and 5xx go through the existing transient-retry layer (`transient.py`). A write that timed out is checked
for having landed before it is retried, as the GitHub adapter does.

## Contract the database provides

What the adapter reads and writes. The private repo may add tables and columns; it must not rename these.

| Table | Columns the adapter uses |
|---|---|
| `projects` | `id`, `key` (unique, e.g. `RW`) |
| `tickets` | `id`, `project_id`, `number` (assigned by the database, unique per project), `title`, `body`, `state` (`open` / `closed`), `close_reason` (`completed` / `not planned`), `labels` (text array), `held_by` (text, null when free), `parent_id`, `created_at`, `updated_at` |
| `ticket_blocks` | `ticket_id`, `blocked_by_id` |
| `comments` | `id`, `ticket_id`, `body`, `author`, `created_at` |

## Tests

- `pm/runway/test/test_runway_db_tracker.py` runs the same scenarios as `test_github_tracker.py` against a fake
  PostgREST server (stdlib `http.server`), including two runners claiming the same ticket where exactly one wins.
- The protocol suite (`memory_adapter.py`) is untouched.
- An optional live test runs only when `RUNWAY_DB_TEST_URL` and a key are set; it is skipped otherwise.

## Not in this spec

The schema SQL, row-level security, clients and projects beyond `key`, runners, time tracking, the page, an MCP
server, importing GitHub or Linear issues, and moving dc-dev-plugins onto runway-db. Those belong to the private repo
or later specs.
