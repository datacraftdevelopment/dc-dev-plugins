---
name: bc-close-out
description: Ship a finished repo task to the Basecamp client face — move its Work item to Shipped (unchecked), leave a one-line plain-English comment, and prepend an entry to the "What shipped" Doc without duplicating its images. Use when the user says "close out", "ship it to Basecamp", "mark it shipped", "update what shipped", or when stepping-away finds a task with a [bc:<id>] token that went live this session. Requires .basecamp/config.json with lists.shipped and docs.what_shipped; stops with a clear message otherwise. Do NOT check the item off — the client does that at the meeting.
---

# bc-close-out — shipping is a move, not a check

**Gate first.** Nothing here runs in a repo without the config.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bc_config.py --require shipped,what_shipped,project_id
```

Exit 2 → tell the user exactly which ids are missing and stop. Exit 1 → no client face, stop.

## Inputs

- The repo task id(s) that went live (from `docs/TASKS.md`, lines carrying `[bc:<id>]`).
- The Basecamp Work item id from that token.
- One plain-English sentence of what the client can now do (voice: `bc-client-face`).
- Screenshots / sample PDF if the change is visible (**show, don't link**).

## Procedure

1. **Read the item** — `basecamp api get /buckets/<project>/todos/<id>.json --json`. Note `description` (it can go missing on a move) and whether every `Ref:` id in the cluster is live.
   - **Partly shipped cluster:** stay in Active; post a `Status:` comment instead of moving. Done.
2. **Move to Shipped**, unchecked:
   `basecamp todos position <id> --to 1 --list <lists.shipped> --json`
   Then re-read with `api get`; if `description` came back empty, restore it with
   `basecamp api put /buckets/<project>/todos/<id>.json -d '{"content":"<title>","description":"<html>"}'`.
3. **Comment** on the item — one line, outcome-first, attachments embedded if visible:
   `basecamp attach <files> --json` → paste the `<bc-attachment>` tags into
   `basecamp api post /buckets/<project>/recordings/<id>/comments.json -d '{"content":"<html>"}'` (inline JSON; `-d @file` is rejected).
4. **Prepend to *What shipped*** — the quirk-safe way:
   ```bash
   S=${CLAUDE_PLUGIN_ROOT}/scripts/doc_roundtrip.py
   basecamp files show <docs.what_shipped> --json --jq '.data.content' > /tmp/bc-body.html
   printf '%s\n' "<h2>YYYY-MM-DD — <outcome title></h2><p>…</p>" > /tmp/bc-entry.html
   python3 $S prepend --entry /tmp/bc-entry.html < /tmp/bc-body.html > /tmp/bc-new.html
   python3 $S check < /tmp/bc-new.html          # no <figure> outside an attachment, or it refuses
   basecamp files update <docs.what_shipped> --title "What shipped" --content "$(cat /tmp/bc-new.html)" --json
   basecamp api get /buckets/<project>/documents/<docs.what_shipped>.json --jq '.updated_at'
   ```
   Always pass `--title`. Confirm with `api get`, not `files show`.
5. **Repo side** — nothing changes in `TASKS.md` beyond what the pm flow already did; the `[bc:<id>]` token is the join. Mention the Basecamp move in the session entry if `stepping-away` is running.

## Never

- Never `basecamp done` a Shipped item. Acceptance is the client's check-off at the meeting.
- Never edit a New request. Comment and tick it, or leave it.
- Never send a fetched Doc body back without `doc_roundtrip.py clean`.
