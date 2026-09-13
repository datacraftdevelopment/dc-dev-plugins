---
name: bc-client-face
description: The DataCraft Basecamp client-face conventions — how a client project is laid out in Basecamp (client's side: New requests + Questions for you; Joe's side: Shipped / Active / Backlog as the status), what a Work item is (a cluster of repo tasks with a Ref footer), how repo TASKS.md lines carry [bc:<id>] tokens, and the plain-English voice. Load BEFORE creating, moving, commenting on, or editing anything in a repo that has a .basecamp/config.json — everything there is client-visible. Also load when the user says "fold this request", "ship this to Basecamp", "what shipped", "client face", "put this in Basecamp", or asks how Basecamp fits the workflow. Do NOT load for repos without .basecamp/config.json, and do not use it for CLI syntax — that is the /basecamp skill's job.
---

# bc-client-face — the conventions

Basecamp is the **client-facing companion** to a repo whose `docs/TASKS.md` is the only
source of truth for work. Nothing is mirrored; the two are joined by ids in both
directions. This skill is the *pattern*. CLI mechanics live in the `/basecamp` skill
(shipped with the basecamp CLI / 37signals plugin); gotchas in `references/quirks.md`.

## Gate — is this repo on the pattern?

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bc_config.py            # parsed config, or exit 1
```

No `.basecamp/config.json` → **stop.** This repo has no client face; don't offer one.
The `pm` plugin never depends on this — Basecamp is opt-in per repo, and some
projects use a different tracker (TC uses Jira) or none.

## The shape of a client project (ADR-0001..0004)

| Side | List | Rule |
|---|---|---|
| **Client's side** (set) | **New requests** | Their words, **never edited**. Folded into a Work item with a comment *"Folded into [title](url)"*, then checked off. |
| | **Questions for you** | One question per line, linking the Work item it gates. Client answers in a comment and ticks it. |
| **Joe's side** (set) | **Shipped** | Live, **unchecked** — the client checks it off at the next meeting. |
| | **Active** | Being built now. Default list in `.basecamp/config.json`. |
| | **Backlog** | Agreed, waiting. An item waiting on an answer stays here with a `Waiting on:` line. |
| **Docs & Files** | *How this project works* · *What shipped* | The explainer (written once) and the batch log (newest on top). |

Only those three tools. Message Board, Card Table, Schedule, Chat stay off.
Enabling tools, client access, and reading the email-in address are **browser-only, once, by Joe**.

## A Work item is a cluster (ADR-0003)

- Outcome-first title in plain English, a description of *what the user can now do*,
  optional `**Status:**` or `**Waiting on:**` line, and an italic last line
  `_Ref: S1 · S5 · S8_` listing every repo task id it absorbs.
- From a request: `**From your request:** [their words](app_url)` in the description.
- Repo side: every absorbed `TASKS.md` line ends with `[bc:<todo id>]`. One Basecamp id → many repo ids.
  (Tracker-neutral form is `[<tracker>:<id>]`; `bc` is this tracker's prefix.)

## Motions

| Motion | What happens | Skill / command |
|---|---|---|
| **Fold** | New request → Work item that links back; comment + check off the request | `basecamp todo … --list <backlog\|active>` then `basecamp comment <req> "Folded into …"` and `basecamp done <req>` |
| **Ship** | Move the Work item to `Shipped`, **unchecked**, one-line plain-English comment; prepend an entry to *What shipped* | `bc-close-out` |
| **Accept** | The client checks the Shipped item off at the meeting | never Joe, never Claude |
| **Ask** | A question the ticket is waiting on goes to *Questions for you*, ticket gets `Waiting on:` and stays in Backlog | `basecamp todo "<question> — [ticket](url)" --list <questions>` |

## Voice — read before writing a single word into Basecamp

Audience is the client. **Outcome-first, plain English.** No file paths, tables, columns,
framework names, or status-machine jargon. "You can now download everything
LiveAuctioneers needs in one click", not "generate the LA CSV via the export handler."
**Show, don't link:** anything visible ships with inline screenshots, reports with a
sample PDF (sandbox data only), attached via `basecamp attach` and embedded as
`<bc-attachment>` tags. Fewer, well-written items beat exhaustive ones; add a to-do only when asked.

## Safety rules (from `references/quirks.md`)

1. **Confirm writes with `basecamp api get …`, not `todos show` / `files show`** — the show commands can serve a stale copy.
2. **Round-tripping a Doc duplicates its images.** Never send a fetched body back raw; use `scripts/doc_roundtrip.py` (see `bc-close-out`).
3. **`files update --content` needs `--title` too** or the title resets to "Untitled".
4. **`todos update --description` may no-op after a `todos position` move.** Use `basecamp api put …/todos/<id>.json` with `content` *and* `description`.
5. **Read first with `--json`** in a repo that points at a live project. There is no sandbox on the Free plan.

## Config contract

`.basecamp/config.json` — the CLI's keys plus two optional blocks only this plugin reads:

```json
{
  "project_id": "…", "todoset_id": "…", "todolist_id": "<active list>",
  "lists": { "shipped": "…", "active": "…", "backlog": "…", "requests": "…", "questions": "…" },
  "docs":  { "what_shipped": "…", "how_it_works": "…" }
}
```

Find ids: `basecamp todolists list --todoset <set-id> --json`, `basecamp files list --json`.
Ids never go in this plugin; they stay in the repo's config and `CLAUDE.md`.

## References

- `references/best-practices.md` — the full conventions writeup (generic part).
- `references/quirks.md` — every API/CLI gotcha hit so far, newest first.
- Design home: `_Tools/Basecamp` (`datacraftdevelopment/dc-basecamp`) — ADRs 0001–0004, discovery log.
