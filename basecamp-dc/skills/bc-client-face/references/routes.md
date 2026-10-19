# Two ways in: the CLI or the connector

A machine reaches Basecamp one of two ways, and some machines have both:

- **The basecamp CLI** (`basecamp` on PATH, logged in). Every machine that runs
  client work has it.
- **The Basecamp connector** (the hosted MCP server; its tools show up as
  `mcp__BaseCamp__*` or similar, named verb_noun: `get_todo`, `create_comment`…).
  Present in claude.ai, cloud sessions, and on machines where it was connected.

## Pick the route at the start of the session

1. `basecamp --version` prints **0.12.0 or later** → use the CLI. It keeps Doc
   bodies in files, so `doc_roundtrip.py` checks them before they are sent.
2. CLI missing or older than 0.12.0, and the connector's tools are listed → use
   the connector, and tell the user once that `basecamp upgrade` brings the CLI
   up to date.
3. Neither → stop and say so. Don't hand-roll HTTP calls.

Why 0.12.0: from that release, rich-text input is **Markdown unless you pass
`--format html`**. The procedures here send HTML when a body carries
`<bc-attachment>` tags or was fetched from Basecamp, and an older CLI has no
`--format` flag to say so. Since 0.13.0 the CLI's own Claude plugin is
`basecamp-cli@37signals` (it was `basecamp@37signals`; the `basecamp` name now
belongs to 37signals' connector plugin).

The conventions, voice and plain-copy rule are the same on both routes. Only the
calls differ.

## The same motion on each route

| Motion | CLI (0.12.0+) | Connector |
|---|---|---|
| Read a to-do, fresh | `basecamp api get /buckets/<p>/todos/<id>.json --json` | `get_todo` |
| New to-do on a list | `basecamp todos create "<title>" --list <list> --description - < desc.md --json` | `create_todo` (`todolist_id`, `content`, `description` in HTML) |
| Edit title / description | `basecamp api put /buckets/<p>/todos/<id>.json --data - < body.json` with `content` **and** `description` | `update_todo` (fields left out are kept) |
| Move to another list (ship) | `basecamp todos position <id> --to 1 --list <list> --json` | `reposition_todo` (`position: 1`, `parent_id: <list>`) |
| Comment | `basecamp comments create <id> - --format html < c.html --json` (or Markdown without `--format`) | `create_comment` (HTML; mentions by person id) |
| Check off (fold-close a request only) | `basecamp todos complete <id>` | `complete_todo` |
| Upload an image or PDF | `basecamp attach <files> --json` → `<bc-attachment>` tags | `create_attachment` (base64) → `attachable_sgid`, embedded as `<bc-attachment sgid="…"></bc-attachment>` |
| Read a Doc body, fresh | `basecamp api get /buckets/<p>/documents/<id>.json --jq '.content'` | `get_document` → `content` |
| Replace a Doc body | `basecamp files update <id> --title "<title>" --content - --format html < new.html --json` | `update_document` (HTML; fields left out are kept) |
| Create a Doc | `basecamp files documents create "<title>" - < body.md --json` | `create_document` |
| Turn on a dock tool | `basecamp tools enable <tool id>` | `enable_dock_tool` |
| Client visibility of one item | `basecamp recordings visibility <id> --visible` | (no connector tool seen yet: use the CLI or the browser) |

Notes:

- Connector tools take record ids, not the project id. `project_id` in
  `.basecamp/config.json` is for the CLI; the list and Doc ids work on both routes.
- The connector takes **HTML** in every rich-text field. Write the HTML yourself;
  there is no Markdown conversion.
- Big bodies on the connector route: write the fetched HTML to a file, run
  `doc_roundtrip.py` on it, and pass the script's output as `content` unchanged.
  Re-read with `get_document` afterwards and run `doc_roundtrip.py check` on what came back.
- Older CLI shortcuts `basecamp todo`, `basecamp comment` and `basecamp done` are
  gone in 0.13.x. Use `todos create`, `comments create`, `todos complete`.
- `-d @file` never worked on `api post/put`; since 0.10.0 `--data -` reads stdin.
