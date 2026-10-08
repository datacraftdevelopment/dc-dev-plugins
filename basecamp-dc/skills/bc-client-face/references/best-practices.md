> Shipped copy for the basecamp-dc plugin. Upstream: `_Tools/Basecamp/docs/basecamp-best-practices.md` (repo `datacraftdevelopment/dc-basecamp`). Edit there, re-copy here, bump the plugin version.

# Basecamp — Best Practices

A living reference for how Basecamp fits into the dev workflow, used by Joe and by Claude (via the Basecamp CLI). Started **2026-06-03** on a client project; written to be portable across repos. Update it as the workflow settles — the "Still evolving" section is where the open questions live.

> Status legend: ✅ settled · 🔄 still evolving

---

## ✅ The model: companion, not source of truth

In-repo markdown stays the detailed, technical source of truth that drives dev work:

- **`docs/TASKS.md`** — active work (Current / Next / Backlog), as technical as needed.
- **`docs/changelog/YYYY-MM-DD.md`** — per-day shipped log (used for billing).

**Basecamp is a companion, not a replacement.** It's a curated, non-technical view for a non-technical audience. The two are not auto-mirrored — they serve different readers, so the same work is phrased differently in each.

## ✅ Audience & voice

- **Audience:** the developer (Joe) + the client (non-technical).
- **Plain English, outcome-first.** Describe *what the user can now do*, not how it's built. No file paths, table/column names, framework terms, or status-machine jargon.
- **Reference voice:** the plain-language client emails (e.g. `docs/2026-05-25-kelsey-email-plain.md`). Friendly, concrete, "you can now…".

| ✅ Write this | ❌ Not this |
|---|---|
| "Download everything LiveAuctioneers needs in one click — the catalog and the photos, renamed automatically." | "Generate the LA tab-delimited CSV + `archiver` image zip via the export route handler." |
| "Each user has their own commission rate — set it under Settings → Users." | "Per-user `commission_rate` column read by `listing-actions.ts`." |

## ✅ Keep it lean

- Add a to-do **only when asked** — typically a task coming out of a client/team meeting.
- **No bulk-importing** the markdown task list and no auto-mirroring. It gets too busy and stops being useful.
- Fewer, well-written items beat exhaustive detail. If it needs deep technical detail, that belongs in `TASKS.md`, not here.

## ✅ Conventions (revised 2026-09-02 — ADR-0002)

- **Tools per project:** exactly three — the **New Requests** to-do set, the **Work** to-do set, and **Docs & Files**. Message Board, Card Table, Schedule, Chat stay off. Tools and client access are switched on in the browser, once, by Joe; the API cannot do it.
- **The client's set** (ADR-0004; *Your side* on the first client project, was *New Requests*) has two lists. **New requests**: raw asks in their own words, **never edited**; when one is folded into work, comment *"Folded into [Work item]"* and check it off — it stays visible and traceable. **Questions for you**: one question per line, each linking the Work item waiting on it; the client answers in the comment and ticks it, Joe folds the answer into the Work item.
- **Work** (*Joe's side* on the first client project) has three lists that are the status, in this order: `Shipped` (live, waiting for the client to check it off), `Active` (being built now), `Backlog` (agreed, waiting). A Work item waiting on an answer **stays in Backlog** with a **`Waiting on:`** line linking its open question(s) and moves to Active when the last one is ticked — never a separate "waiting" list (ADR-0004).
- **Shipping is a move, not a check.** When work goes live: `todos position <id> --to 1 --list <shipped-id>` plus a one-line plain-English comment. The item stays **unchecked**. At the next meeting the client tries it and checks it off herself. Partly-shipped clusters stay in Active with a status comment until every ref is live.
- **Meeting rhythm:** review Shipped together → go through what's new → after the call, write the agreed work into Active / Backlog. Don't type into Basecamp during the call.
- **A Work item is a cluster** (ADR-0003): what ships together, outcome-first title, plain-English description, an optional **Status:** or **Waiting on:** line (links to the client-side question(s), ADR-0004), and an italic last line `_Ref: S1 · S5 · S8_` listing every repo task id it absorbs. When it came from a request, the description links back: `**From your request:** [their words](app_url)`.
- **Repo side:** every absorbed `TASKS.md` line carries `[bc:<todo id>]` at the end. One Basecamp id → many repo ids.
- **Assignee / due dates:** default owner (Joe) — leave both off; it's understood. Only set a due date when there's a real, firm deadline.
- **Descriptions and comments accept Markdown** (bold, lists, links) — the CLI converts to HTML. Use light formatting for scannability.
- **Show, don't link (Joe, 2026-09-02).** Anything visible — a shipped screen, a report — carries **screenshots inline, and a sample PDF for reports**, so Joe can show the client from Basecamp without either of them logging into the app. Generate from sandbox data (never a real client's), save under the client repo's `docs/samples/YYYY-MM-DD-*`, upload with `basecamp attach <files> --json` (account-scoped; returns `<bc-attachment>` tags) and embed those tags in the doc body or a comment. Comments with attachments go through `basecamp api post /buckets/<p>/recordings/<id>/comments.json -d '{"content":"<html>"}'` (`-d @file` is not supported — pass the JSON inline). First use: the Cronin reports entry in *What shipped* + a comment on the Shipped item, 2026-09-02.

## ✅ How Claude works with Basecamp (CLI)

Edits are made through the Basecamp CLI (the `/basecamp` skill). Per-repo `.basecamp/config.json` pins the project and default list so commands don't need `--in`:

```json
{ "project_id": "<id>", "todolist_id": "<active-list-id>" }
```

Common commands:

```bash
basecamp todo "Plain-English title" --description "..." --json   # add to default (Active) list
basecamp todo "..." --list <backlog-id> --json                    # add to Backlog
basecamp todos list --json                                        # list the default list
basecamp recordings todos --in <project> --json \
  --jq '.data[] | select(.parent.title=="New Requests")'          # the client's raw requests (loose, no list)
basecamp comment <id> "Folded into **[title](url)**" --json       # trace a request to its Work item
basecamp todos position <id> --to 1 --list <shipped-id> --json    # ship: move to Shipped (stays unchecked)
basecamp done <id>                                                # the client's move at the meeting (or fold-close a request)
basecamp files update <doc-id> --content "..." --title "..." --json  # ALWAYS pass --title too: --content alone resets it to "Untitled"
basecamp todolists list --todoset <work-set-id> --json            # find list IDs (two sets → --todoset required)
basecamp files doc create "Title" "Markdown body" --json          # create a Doc (Markdown converted since CLI 0.7)
```

Projects with two to-do sets make `todo` and `todolists list` ambiguous — pin `todolist_id` in `.basecamp/config.json` or pass `--list` / `--todoset`. Full list of gotchas: `docs/quirks.md`.

Always pass `--json` (or `--md` when showing results to a human). Filter with the built-in `--jq`, never an external `jq`.

## ✅ Client-facing changelog → Basecamp Docs

Decided 2026-06-03. Plain-language product updates live in a single living Basecamp **Document** titled **"What's New"** (newest entry on top), separate from the technical per-day `docs/changelog/` (which stays the detailed billing/dev record).

- Write entries like the client emails: "you can now…", outcomes not implementation. No file paths, table names, or jargon.
- **Append to the TOP** of the existing doc — don't create a new doc per update. Update via the CLI:
  `basecamp files update <doc_id> --content "<full new HTML>"`
- **Documents accept Markdown as of CLI 0.7.2** (verified 2026-09-02: `files doc create` with a Markdown body rendered as `<h2>`, `<ul>`, `<strong>`). The June note that Docs needed hand-written HTML is obsolete. For long bodies pass `"$(cat file.md)"` to avoid shell-quoting issues.
- **Two docs per client project:** *How this project works* (the explainer, written once) and *What shipped* (append newest on top; replaces the message board for batch summaries — ADR-0002).

## 🔄 Still evolving (open questions)

Being worked out — don't hard-code a workflow around these yet:

- **In-flight visibility** — does the client see a **Status:** line on Active items, or only agreed + shipped? (AgentTest showed Status lines; Kelsey's reaction decides.)
- **Triage cadence and owner** — before each meeting, or daily by an agent; whose approval closes a raw request.
- **Email-in** — forwarded threads carry several asks; does triage split them, and does the client see the split. The email-in address is UI-only.
- **Feedback** — where client feedback on shipped work is captured (comment on the checked item is the lean default).
- **verify-before-done** — whether "checked in Basecamp" is part of *done* for a shipped task.

Settled 2026-09-02 and moved above the line: tools per project, request/work split, fold rule, cluster granularity, Docs over message board.

## 🔄 Goal: reusable across repos

Once the flow settles here, distill this into a repo-agnostic template to drop into other projects. Keep generic guidance above the line; keep project-specific IDs in the per-repo section below.

---

Per-repo ids live in each repo's `.basecamp/config.json` and `CLAUDE.md`, never here.
