# basecamp-dc — the Basecamp client-face layer

Opt-in per repo. If a repo has no `.basecamp/config.json`, this plugin is inert:
no hook output, no skill triggers, nothing. Some DataCraft projects use Basecamp as
the client face (one client so far), some use another tracker (TC uses Jira), most use none.
**`pm` never depends on this plugin**, and this plugin never reaches into `pm`.

## What it assumes

- The **basecamp CLI** (`brew install basecamp/tap/basecamp` or per basecamp.com), authenticated on this machine
  (`basecamp setup` / `basecamp auth`; `basecamp accounts use` picks the default account — one login per machine, so
  the TC machine and the DataCraft machine each authenticate to their own account).
- The CLI's own **`/basecamp` skill** for command syntax — installed by `basecamp setup` into `~/.claude/skills/basecamp`,
  or as `basecamp@37signals` from `/plugin marketplace add basecamp/claude-plugins`. Keep one of the two, not both.
- `python3` on PATH (stdlib only).

## What it adds

| Piece | Job |
|---|---|
| `skills/bc-client-face` | The conventions: client's side / Joe's side, Shipped-Active-Backlog as the status, clusters with `Ref:` footers, `[bc:<id>]` tokens, the plain-English voice, the safety rules. Ships copies of `best-practices.md` and `quirks.md`. |
| `skills/bc-close-out` | Ship a task: move to Shipped unchecked, comment, prepend to *What shipped* without duplicating images. Runs only on the user's yes — session close never writes by itself. |
| `skills/bc-setup` | Opt-in seam to pm: with a valid config present, install `docs/agents/client-face.md` from `templates/` when absent (hand edits win, symlink destinations refused). pm's `stepping-away` reads that contract; pm never names Basecamp. |
| `hooks/session-start.sh` | When the repo has the config, one paragraph of context (project, list ids). Finds the root via `CLAUDE_PROJECT_DIR`, the event cwd, or its git toplevel. Silent otherwise. |
| `scripts/bc_config.py` | Reads/validates the config; `--require` names missing ids; `--context` feeds the hook. |
| `scripts/bc_setup.py` | The bc-setup helper. Requires the existing config, installs the bundled contract only if absent, no network. |
| `scripts/doc_roundtrip.py` | `clean` / `prepend` / `check` a Doc body so attachments don't multiply on every save. |

## Config contract

The CLI's `.basecamp/config.json` plus two optional blocks only this plugin reads:

```json
{
  "project_id": "…", "todoset_id": "…", "todolist_id": "<active list id>",
  "lists": { "shipped": "…", "active": "…", "backlog": "…", "requests": "…", "questions": "…" },
  "docs":  { "what_shipped": "…", "how_it_works": "…" }
}
```

## Planned, not built

`bc-fold`, `bc-reconcile`, `bc-meeting-pass` — each gets written when the manual pass stops holding, not before.

## Design home

Decisions (ADR-0001..0004), the discovery log, and the upstream `best-practices.md` / `quirks.md` live in
`_Tools/Basecamp` (`datacraftdevelopment/dc-basecamp`). Edit there, re-copy into `skills/bc-client-face/references/`, bump the version here.
