# Migrating a project to pm 0.8

pm 0.8 re-shaped the plugin around Matt Pocock's skills (see `WORKFLOW.md`). Three `_pm/` files stopped being sources of truth. Nothing is deleted for you; this note says what to do with a project that carries the old layout.

| Old | Now | What to do |
|---|---|---|
| `_pm/TASKS.md` | Work items live on the tracker (GitHub Issues, or `.scratch/` local markdown via `/setup-matt-pocock-skills`). The session file's Intent block carries "what I'm picking up today." | Move live items to the tracker — as wayfinder tickets if they're decisions, implementation tickets if they're builds. Then delete the file, or leave it with a top line `> Legacy — not maintained since <date>`. The rituals read it as a hint only. |
| `_pm/decisions/` | `docs/adr/` (Matt's `/domain-modeling` format); decisions reached in a wayfinder ticket live on that ticket. | `git mv _pm/decisions docs/adr` — the format is close enough. Add a `status:` line if missing. |
| `_pm/context-map.md` | Dropped. `CLAUDE.md` names the sources that matter; `docs/agents/domain.md` (from Matt's setup) says how domain docs are read. | If any row carried a rule a session still needs, move it into `CLAUDE.md`. Delete the file. |
| `_pm/sessions/YYYY-MM-DD.md` | `_pm/sessions/YYYY-MM-DD-<name>.md` — per person, append-only. | Old files stay as they are; new ones get the suffix. |
| `_pm/dashboard.html` (v1, tasks/milestones) | v2 stage board, local-only. | Add `_pm/dashboard.html` to `.gitignore`; `git rm --cached` it if committed. Re-render — the v2 template is stamped automatically. |
| (nothing) | `docs/intent/<slug>.md` — one per stream, from `discovery`. | Create `docs/intent/`. For work already in flight, a short retroactive intent per stream gives the stage board something to derive from — optional. |
| (nothing) | Tracker wiring — `docs/agents/issue-tracker.md`. | Run `/setup-matt-pocock-skills` once per repo. |

Skill renames: `brainstorm-lite` → `discovery` (different job: riff to an intent, not plan-small). `verify-before-done`, `okf`, `whats-next`, `checkpoint`, `stepping-away` keep their names.

`pm/template/` (the scaffold) lags this note until the DC-Project-Builder is updated — freshly scaffolded projects get the old `_pm/` files too; treat them per the table.
