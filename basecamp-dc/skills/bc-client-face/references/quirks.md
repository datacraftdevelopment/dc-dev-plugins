> Shipped copy for the basecamp-dc plugin. Upstream: `_Tools/Basecamp/docs/quirks.md` (repo `datacraftdevelopment/dc-basecamp`). Edit there, re-copy here, bump the plugin version.

# Quirks

Non-obvious gotchas worth remembering. Check before re-inventing fixes.

> Format: short heading, one or two sentences. Date-stamped. Add new entries at the top. The point is fast scanning, not exhaustive documentation.

## 2026-09-10 — Round-tripping a Doc duplicates its images

- **`files show` → edit → `files update` leaves a loose copy of every image.** The API returns each `<bc-attachment>` with its rendered `<figure><img><figcaption>` inside; send that back and Basecamp keeps the attachment *and* re-emits the inner figure as a separate `<figure dir="auto">` after it. Each save adds another set (a client's *What shipped*: 23 attachments had become 43 figures after a week of prepends). Before sending, empty every attachment — `re.sub(r'(<bc-attachment\b[^>]*>).*?(</bc-attachment>)', r'\1\2', html, flags=re.S)` — and drop any remaining top-level `<figure>`. Check after: `<figure` count == `<bc-attachment` count.

## 2026-09-02 — Basecamp API/CLI limits found in the AgentTest dry run

- **`basecamp attach` works and embeds.** Six PNG/PDF files uploaded account-scoped; the returned `<bc-attachment>` HTML pasted into a Doc body (`files documents create`) and a comment (`api post …/comments.json`) rendered as inline images / file cards. `-d @file` is rejected by `api post` ("invalid character '@'") — pass `-d "$(cat file.json)"`.
- **`todos position --to 1 --list <shipped>` moves the item but the description survived empty on the first Shipped item** (Cronin reports had no description after the move; the Active items kept theirs). Re-check `description` after a move and re-set it with `todos update --description`.

- **`todos update <id> --description` can return `ok: true` and change nothing** (2026-09-03, on a to-do that had just been moved to Shipped with `todos position`; the old description with its stale *Status:* line stayed put through two attempts). `basecamp api put /buckets/<p>/todos/<id>.json -d '{"content":"<title>","description":"<html>"}'` applied it first time — pass `content` (the title) as well, and re-read with `todos show --json` to confirm.
- **…but `todos show` can serve a stale cached copy right after an update** (2026-09-10, a client to-do: three "failed" description updates had all landed — `todos show` kept returning the pre-edit body while `basecamp api get /buckets/<p>/todos/<id>.json` showed the new one and a fresh `updated_at`). Confirm writes with `api get`, not `todos show`; the "change nothing" cases above may partly be this.
- **`files update <doc> --content` resets the title to "Untitled".** Always pass `--title` in the same call.
- **A to-do's `title` field is a ~100-char display truncation** ending in `...`; the real text is `content`, untruncated. Don't "fix" a title that looks cut off in `--jq '.data.title'`.
- **Moving a to-do between lists works:** `todos position <id> --to 1 --list <list-id>` (same project only). This is the "ship" motion.

- **Dock tools are UI-only.** Enabling Message Board / Card Table / Schedule has no API; `PUT /buckets/:id/dock/:tool.json` 404s. Turn tools on in the browser before an agent needs them.
- **Client access is UI-only.** `PUT /projects/:id.json {"clients_enabled":true}` returns 200 and changes nothing. Until it is on, `recordings visibility --visible` returns `forbidden`.
- **A to-do set can hold loose to-dos with zero lists.** `todolists list` for that set returns null and the CLI's `--jq '.data[]'` errors; the items are still there (`recordings todos --in <project>` finds them, `parent.type == "Todoset"`).
- **Email-in addresses are not in the API** (not on todoset or todolist JSON). Read them from the UI.
- **`basecamp projects --json` prints command help, not projects.** Use `basecamp projects list --json`. Same for `people` → `people list`. There is no `whoami`; use `auth status`.
- **Multiple to-do sets in one project** make `todolists list` and `todo` ambiguous — pass `--todoset <id>` or `--list <id>`; a pinned `todolist_id` in `.basecamp/config.json` resolves it.
- **To-do lists cannot be repositioned via the API.** `PUT /buckets/<p>/todolists/<id>/position.json` 404s (2026-09-03). A newly created list lands at the top of its set; drag it in the UI.
- **`todos position` accepts a `--to` past the end of the target list** and appends; count the list first (`todos list --list <id> --all`) to place at the end deterministically.
- **A document's `content` can read back empty through the API** while the UI shows it (a client's *How this project works* doc, 2026-09-03 — `documents/<id>.json` returned `content: ""` after the 09-02 write). Documents keep versions in the UI, so a `files update` is recoverable, but look in the browser before overwriting.
