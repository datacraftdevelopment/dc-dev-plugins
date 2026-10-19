---
name: bc-close-out
description: Ship a finished repo task to the Basecamp client face — move its Work item to Shipped (unchecked), leave a one-line plain-English comment, and prepend an entry to the "What shipped" Doc without duplicating its images. Use when the user says "close out", "ship it to Basecamp", "mark it shipped", "update what shipped", or approves the step stepping-away offers from docs/agents/client-face.md. Requires user authorization plus .basecamp/config.json with lists.shipped and docs.what_shipped; stops with a clear message otherwise. Do NOT check the item off — the client does that at the meeting.
---

# bc-close-out — shipping is a move, not a check

**Authorization first.** Every step below writes to a client-visible project.
An explicit request to perform this close-out already authorizes it; preserve
that authorization across turns and do not ask again. `stepping-away` finding
a shipped item, or a session ending, authorizes nothing on its own. If the
client update has not been authorized, prepare the concrete update and ask
before sending it.

**Load before writing.** Read `bc-client-face` (conventions, voice, safety rules)
and pick the route with its `references/routes.md`: the CLI when `basecamp
--version` is 0.12.0 or later, otherwise the Basecamp connector. On the CLI route
also load the CLI's own `basecamp` skill for syntax. No write happens before that.
Each step below gives the CLI call first and the connector call after it.

**Gate.** Nothing here runs in a repo without the config:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bc_config.py" --require shipped,what_shipped,project_id
```

Exit 2 → tell the user exactly which ids are missing and stop. Exit 1 → no client face, stop.

## Inputs

- The ticket file path — or the commit, for a ticketless change — for each item
  that went live.
- The Basecamp Work item id from the ticket's `Client-ref:` line. (A repo that
  explicitly keeps `docs/TASKS.md` as its tracker carries the same id
  as a `[bc:<id>]` token on the task line.) No mapping → never guess an id; ask
  which Work item it is, or record the step skipped.
- One plain-English sentence of what the client can now do, swept against the
  plain-copy rule (`bc-client-face/references/plain-copy.md`) before it is posted. The
  same sweep covers the *What shipped* entry.
- Screenshots / sample PDF if the change is visible (**show, don't link**).

## Procedure

1. **Read the item** — `basecamp api get /buckets/<project>/todos/<id>.json --json` (connector: `get_todo`). Note `description` (it can go missing on a move) and whether every `Ref:` id in the cluster is live.
   - **Partly shipped cluster:** stay in Active; post a `Status:` comment instead of moving. Re-read the comment (`api get`, or the connector's `list_comments`) and verify its text, then report done; no Doc entry is needed yet.
2. **Move to Shipped**, unchecked:
   `basecamp todos position <id> --to 1 --list <lists.shipped> --json`
   (connector: `reposition_todo` with `position: 1`, `parent_id: <lists.shipped>`).
   Then re-read; if `description` came back empty, restore it with
   `basecamp api put /buckets/<project>/todos/<id>.json -d '{"content":"<title>","description":"<html>"}'`
   (connector: `update_todo` with `description`).
3. **Comment** on the item — one line, outcome-first, attachments embedded if visible:
   `basecamp attach <files> --json` → put the `<bc-attachment>` tags in `/tmp/bc-comment.html`, then
   `basecamp comments create <id> - --format html < /tmp/bc-comment.html --json`.
   Connector: `create_attachment` per file → `<bc-attachment sgid="<attachable_sgid>"></bc-attachment>`
   in the HTML passed to `create_comment`.
4. **Prepend to *What shipped*** — the quirk-safe way. Fetch the body **fresh
   from the API** (`api get`; the `files show` command can serve a stale cached
   copy and must not feed a write):
   ```bash
   S="${CLAUDE_PLUGIN_ROOT}/scripts/doc_roundtrip.py"
   basecamp api get /buckets/<project>/documents/<docs.what_shipped>.json --jq '.content' > /tmp/bc-body.html
   ```
   **Stop if `/tmp/bc-body.html` is empty** unless the user confirms this Doc is
   genuinely new and empty — an empty fetch of a Doc that has entries means a
   bad id or a bad fetch, and writing would wipe it.
   ```bash
   printf '%s\n' "<h2>YYYY-MM-DD — <outcome title></h2><p>…</p>" > /tmp/bc-entry.html
   python3 "$S" prepend --entry /tmp/bc-entry.html < /tmp/bc-body.html > /tmp/bc-new.html
   python3 "$S" check < /tmp/bc-new.html          # no <figure> outside an attachment, or it refuses
   basecamp files update <docs.what_shipped> --title "What shipped" --content - --format html < /tmp/bc-new.html --json
   basecamp api get /buckets/<project>/documents/<docs.what_shipped>.json --jq '.content' > /tmp/bc-verify.html
   ```
   **Connector route:** `get_document` → write its `content` to `/tmp/bc-body.html`,
   run the same empty check, `prepend` and `check`, pass `/tmp/bc-new.html` unchanged
   as `content` to `update_document`, then `get_document` again into `/tmp/bc-verify.html`
   and run `check` on it.
   Always pass `--title` (CLI). Without `--format html`, CLI 0.12.0+ reads the body as
   Markdown. Verify by **content, not timestamp**: `/tmp/bc-verify.html`
   must contain the new entry's heading and the entries that were already there
   (`updated_at` alone proves nothing about what landed).
5. **Repo side** — the ticket keeps its `Client-ref:` line (or the `TASKS.md`
   line its `[bc:<id>]` token) untouched; that join is the record. Report the
   step done / skipped / blocked in the session entry if `stepping-away` is running.

## Never

- Never write to Basecamp without authorization covering that client update; existing authorization remains valid.
- Never complete a Shipped item (`todos complete`, `complete_todo`). Acceptance is the client's check-off at the meeting.
- Never edit a New request. Comment and tick it, or leave it.
- Never send a fetched Doc body back without `doc_roundtrip.py clean`.
- Never feed a write from a `files show` / `todos show` body — fetch fresh with `api get` or the connector's `get_*`.
