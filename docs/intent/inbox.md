# Inbox — loose asks and ideas, not yet shaped

One line per item. Dated, sourced, in client-safe words. No status, no
progress — this is not a task list. A line leaves this file only by becoming
an intent (`discovery`), merging into an item that already exists, or being
retired with a reason in the session entry. `whats-next` reads it as the
ungroomed list and asks about anything older than four session opens or when
the file passes twelve lines.

Format: `- YYYY-MM-DD · <source> · <the ask, one line>`

- 2026-07-15 · TASKS.md (legacy) · RCC_Agent-Workflow: restore Joe's overwritten 2026-07-15 session entry from Dropbox version history, then merge the harness entry around it. Repo is not under Agentic-Mini; find it first.
- 2026-07-15 · TASKS.md (legacy) · Confirm `_RCC/_FM-Workflow/` is gone (superseded by RCC_Agent-Workflow). Not found under Agentic-Mini on 2026-09-13; if it only lived in Dropbox, nothing to do.
- 2026-07-15 · TASKS.md (legacy) · Workshop file: regenerate its export script from the current template (fm-dc shipped v4 in 0.5.4 and a v5 pair in 0.7.0) and re-paste; the file was on v3 when this was written.
- 2026-07-15 · TASKS.md (legacy) · Decide on `project-snapshots` (git-less folder checkpoints, from the old fm-starter): fold into fm-dc's SaXML patch/rollback or drop. fm-starter itself is not under Agentic-Mini on 2026-09-13 — if it went with Dropbox, drop.
- 2026-07-15 · TASKS.md (legacy) · Update fm-dc to 0.8.1 on the other Mac (this one went 0.7.1 → 0.8.1 on 2026-09-13) and confirm `pip3 install lxml requests python-dotenv` there.
- 2026-07-15 · TASKS.md (legacy) · Confirm the old fm-starter is retired: BE/MBS extracted, nothing unique left (fmlint, fmsavexml, fmserver, the generic filemaker skill are superseded by fm-dc). Not found under Agentic-Mini on 2026-09-13.
- 2026-09-14 · client session · Orchestrator + parallel build lanes as a standard pm pattern. Field notes collecting in `docs/intent/pm-018-orchestrator-lanes.md`; run discovery once it has a few days behind it.
- 2026-07-15 · TASKS.md (legacy) · Scope or drop `genobj` (fm-dc `tools/genobj/`, Phase-3 stub, still "not yet built" per its README on 2026-09-13). A discovery call, not a ticket.
- 2026-09-20 · pm-021 session · Orchestration engine (loop in code, judgment as stateless Ringer steps around `build-swarm`'s `loop.py`). Parked sketch: `docs/research/orchestration-engine-concept.md`. Pick up only if a pm 0.21 run shows the lead seat still out-spending its workers.
- 2026-10-04 · playbook-review session · `credential-guard`: should `git update-ref` be allowed? It was blocked as an unknown subcommand while moving `main` to a commit built in a temporary worktree; `git reset --soft <sha>` did the same job and is already allowed.
- 2026-10-04 · sdlc-plugin session · `credential-guard`: let a rebase finish without opening an editor. After a conflict was resolved, `git -c core.editor=true rebase --continue` and `GIT_EDITOR=true git rebase --continue` were both blocked (config and environment prefixes); `git commit --reuse-message=<sha>` followed by a plain `git rebase --continue` worked. Allow one narrow form, or put the workaround in the block message.
- 2026-10-04 · sdlc-plugin session · Record token use per session in the session entry, so the "Did it help?" rows in `docs/changes/README.md` get numbers (pm 0.21 records it for orchestrated runs only). Raised as a pm mod idea; mods need Claude Code 2.1.287 and this Mac is on 2.1.285. `_Tools/TokenUsage` already has per-session detail, so try pulling the figure from it at `stepping-away` before building a mod.
- 2026-10-08 · runway-status session · Runway panel: the phase strip (five bars: sync, prep, agent, check, merge) labels only the current step, and Joe couldn't tell what the bars meant. Label all five, or add a tooltip.
