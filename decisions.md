# Decisions

- 2026-10-05 · Start with a deterministic script as the manager, not an LLM manager. Management by script costs no tokens and is readable; PM's own pm-021 measured 2.6x usage when an orchestrator was the default. Hermes stays the LLM-manager comparison.
- 2026-10-05 · First experiment runs headless `claude -p` on the host in git worktrees, not Sandcastle in Docker. It removes container auth and Docker from the first test; Sandcastle is experiment 02 once the loop shape is proven.
- 2026-10-05 · Judgment is declared on the ticket at planning time (`Gate: human`) rather than discovered by the agent mid-run. Discovered blockers still park as `needs-human`.
- 2026-10-05 · Reuse pm's tracker format unchanged, adding only `Gate:` and `Branch:` header lines.
- 2026-10-05 · Approvals must land in the tracker, not arrive as relayed messages. The first real run showed the Mac's auto-mode check rejects a go relayed through another Claude session. Experiment 03 has a decision tap edit the ticket (or a Linear/GitHub status), and Runway picks it up on its schedule.
