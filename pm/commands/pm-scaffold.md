---
description: Scaffold a project from the datacraft PM starter — client engagement, personal project, or in-place _pm/ for an existing folder — and run the skeleton interview.
argument-hint: <ClientName> | self <ProjectName> | here
---

# /pm-scaffold

Stand up a project from the bundled starter. Three moves: **copy → rename → orient**. Do them in order; don't skip the interview.

The argument is: **$ARGUMENTS**

## 1. Resolve the mode and name

Three modes — read the argument (and the user's phrasing) to pick one:

| Mode | Trigger | Target |
|---|---|---|
| **Client** (default) | A bare name: `Acme` | `datacraft-<ClientName>/` |
| **Personal** | `self` / `personal` / "for me" / "no client", plus a name: `self HomeLab` | `<ProjectName>/` — no prefix; `datacraft-` is reserved for client work |
| **In-place** | `here`, `.`, "this folder" | `_pm/` added to the current directory |

- If `$ARGUMENTS` is empty, ask ONE question: *"What are we standing up? A client name (→ `datacraft-<Client>/`), a personal project (`self <Name>` → plain `<Name>/`), or `here` to add `_pm/` to this folder."* **A missing client is never a blocker** — personal and in-place modes don't have one.
- Normalise the name to a folder-safe token (strip spaces/punctuation, keep it readable — "Acme Corp" → `AcmeCorp`).
- New-folder modes create the target **in the current working directory**. If the target folder already exists, stop and tell the user — don't overwrite.
- In-place mode: if `./_pm/` already exists, stop — this folder is already scaffolded.

## 2. Copy the template

The starter lives inside this plugin.

**Client / personal** — copy it wholesale:

```bash
cp -R "${CLAUDE_PLUGIN_ROOT}/template/." "./<TargetFolder>/"
find "./<TargetFolder>" -name .DS_Store -delete
```

**In-place** — copy ONLY `_pm/`; never touch the folder's existing files:

```bash
cp -R "${CLAUDE_PLUGIN_ROOT}/template/_pm" "./_pm"
find "./_pm" -name .DS_Store -delete
```

The `whats-next` and `stepping-away` skills are **not** in the template — they ship globally with this plugin and are already available. Don't copy them in.

## 3. Rename the placeholder

*(Skip for in-place — nothing outside `_pm/` was copied.)*

The template's `CLAUDE.md` opens by describing itself as a starter. In the **copied** `CLAUDE.md`:

- Replace the "This is a STARTER, not a live project" banner with a one-line project header naming the client (or personal project) and today's date.
- Replace remaining literal `datacraft-Project` references with the target folder name.
- **Personal mode:** where the doc's intro reads wrong without a client ("client engagement"), soften to "project" — touch only the lines that read wrong, don't rewrite the doc.
- Leave the rest of the structure doc intact — it still describes the layout correctly.

Also set the `README.md` title to the project name.

## 4. Run the skeleton interview

`_pm/skeleton.md` is the default planning artifact (Wei Hao's 5-step) — every mode gets one. Don't leave it as a placeholder — interview the user, briefly. Ask these one at a time, conversationally, and keep it short (a change-request job only needs a paragraph):

1. **Outcome sentence** — when this project is done, what's true that wasn't before?
2. **Critical user journey** — the one path through the deliverable that has to work.
3. **Minimum capabilities** — the few things that path requires. (Only what would *break the journey* if removed.)
4. **Fundamental enablers** — what has to exist underneath (data, access, integrations)?
5. **Non-negotiables** — hard constraints (deadline, budget, tech, compliance).

Write the answers into the new folder's `_pm/skeleton.md` (in-place: `./_pm/skeleton.md`) in that 5-step structure. If the user says it's a small job, collapse it to a single tight paragraph rather than five headings — the artifact scales with content.

## 5. Sign off

Confirm what you did in 3–4 lines: what was created (new folder or in-place `_pm/`), renames done, skeleton captured. Then point at the next step: *"Drop discovery artifacts in `_pm/artifacts/`, add tasks to `_pm/TASKS.md`, and run `whats-next` when you start a working session."*

Don't start doing project work — scaffolding ends here.
