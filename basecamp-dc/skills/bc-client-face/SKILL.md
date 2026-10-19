---
name: bc-client-face
description: "The DataCraft Basecamp client-face conventions — how a client project is laid out in Basecamp (client's side: New requests + Questions for you; Joe's side: Shipped / Active / Backlog as the status), what a Work item is (a cluster of repo tickets with a Ref footer), how tickets carry the join (Client-ref lines, or [bc:<id>] tokens in a repo that keeps TASKS.md as its tracker), and the plain-copy rule every word written there follows. Load BEFORE creating, moving, commenting on, or editing anything in a repo that has a .basecamp/config.json — everything there is client-visible. Also load when the user says \"fold this request\", \"ship this to Basecamp\", \"what shipped\", \"client face\", \"put this in Basecamp\", or asks how Basecamp fits the workflow. Do NOT load for repos without .basecamp/config.json, and do not use it for CLI syntax — that is the /basecamp skill's job."
---

# bc-client-face — the conventions

Basecamp is the **client-facing companion** to the repo's own tracker — pm's
ticket files, or a hand-kept `docs/TASKS.md` when the repo explicitly
names that as its tracker. The tracker stays the source of truth for work; nothing
is mirrored, the two are joined by ids in both directions. This skill is the *pattern*. CLI mechanics live in the CLI's own
`basecamp` skill (the `basecamp-cli@37signals` plugin); gotchas in `references/quirks.md`.

**Two routes.** A machine reaches Basecamp through the basecamp CLI, the Basecamp
connector (its `get_todo`, `create_comment`… tools), or both. Pick one at the start
of the session with `references/routes.md`: the CLI when `basecamp --version` is
0.12.0 or later, otherwise the connector if its tools are listed. That file maps
every motion below to both.

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
- Repo side: every absorbed ticket carries the join — a `Client-ref:` line in a pm
  ticket file, or a `[bc:<todo id>]` suffix on the task line in a repo that keeps
  `docs/TASKS.md` as its tracker. One Basecamp id → many repo ids.
  (Tracker-neutral form is `[<tracker>:<id>]`; `bc` is this tracker's prefix.)

## Motions

| Motion | What happens | Skill / command |
|---|---|---|
| **Fold** | New request → Work item that links back; comment + check off the request | `basecamp todos create … --list <backlog\|active>` then `basecamp comments create <req> "Folded into …"` and `basecamp todos complete <req>` (connector: `create_todo`, `create_comment`, `complete_todo`) |
| **Ship** | Move the Work item to `Shipped`, **unchecked**, one-line plain-English comment; prepend an entry to *What shipped* | `bc-close-out` |
| **Accept** | The client checks the Shipped item off at the meeting | never Joe, never Claude |
| **Ask** | A question the ticket is waiting on goes to *Questions for you*, ticket gets `Waiting on:` and stays in Backlog | `basecamp todos create "<question>" --list <questions> --description "[ticket](url)"` (connector: `create_todo`) |

## Voice — read before writing a single word into Basecamp

Audience is the client, who does not work in software. **Every line follows the
plain-copy rule in `references/plain-copy.md`: read it before the first write of a
session, and run its sweep on every title, description, comment and Doc entry before
it lands.** If the repo has `docs/plain-copy-rule.md`, read that too; it names this
client's own words and wins where it is more specific.

The rule in one line: write plainly what happens, in complete sentences, using only
the client's own words and the names on their screens. No metaphors, idioms, coined
labels, fragments without a verb, or our words (export, sync, API, sandbox, deploy…).
The test is reading the line aloud to the client on the phone: if they would ask
"what does that mean?", rewrite it. "You can now download everything
LiveAuctioneers needs in one click", not "generate the LA CSV via the export handler."
**Show, don't link:** anything visible ships with inline screenshots, reports with a
sample PDF (sandbox data only), attached via `basecamp attach` (connector: `create_attachment`) and embedded as
`<bc-attachment>` tags. Fewer, well-written items beat exhaustive ones; add a to-do only when asked.

## Safety rules (from `references/quirks.md`)

1. **Confirm writes with a fresh read** — `basecamp api get …` (or the connector's `get_todo` / `get_document`), not `todos show` / `files show`, which can serve a stale copy. Check the content, not just `updated_at`.
2. **Round-tripping a Doc duplicates its images.** Never send a fetched body back raw, on either route; use `scripts/doc_roundtrip.py` (see `bc-close-out`).
2a. **HTML needs `--format html` on CLI 0.12.0+.** Rich text is Markdown by default; a fetched body or one with `<bc-attachment>` tags goes in as HTML. The connector always takes HTML.
3. **Pass `--title` with `files update --content`.** Older CLIs reset the title to "Untitled"; 0.13 says it keeps it, but the extra flag costs nothing.
4. **`todos update --description` may no-op after a `todos position` move.** Use `basecamp api put …/todos/<id>.json` with `content` *and* `description` (connector: `update_todo`), then re-read.
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

Find ids: `basecamp todolists list --todoset <set-id> --json`, `basecamp files list --json` (connector: `list_todolists`, `list_documents`).
`project_id` is for the CLI; connector tools take the list and Doc ids directly.
Ids never go in this plugin; they stay in the repo's config and agent instructions.

## Session close (pm seam)

The `bc-setup` skill installs `docs/agents/client-face.md` (only when absent —
the file is hand-owned afterwards). pm's `stepping-away` reads that contract at
close and offers the matching `bc-close-out` step; nothing is written to
Basecamp without authorization covering that update; an explicit request already authorizes it. pm itself never names Basecamp.

## References

- `references/best-practices.md` — the full conventions writeup (generic part).
- `references/routes.md` — CLI or connector: how to pick, and each motion on both.
- `references/plain-copy.md` — the plain-copy rule and the sweep every Basecamp write gets.
- `references/quirks.md` — every API/CLI gotcha hit so far, newest first.
- Design home: `_Tools/Basecamp` (`datacraftdevelopment/dc-basecamp`) — ADRs 0001–0004, discovery log.
