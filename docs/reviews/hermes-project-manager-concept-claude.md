<!-- Original Claude Fable discussion report, preserved without edits.
Run: hermes-pm-concept-discussion-20260915T110303Z-p72391
Date: 2026-09-15
One attempt; delivery-contract check passed. This verifies report structure, not judgment or live integration behavior.
Source note: ../research/hermes-project-manager-concept.md
-->

# Hermes project-manager concept — light review

Source: `hermes-project-manager-concept.md` (2026-09-15), plus `pm/WORKFLOW.md`, `pm/skills/session-succession/SKILL.md`, and `docs/intent/pm-019-session-succession.md`. All Hermes claims here are documentation-based (the note's H1–H5), not observed behavior.

## Recommendation

Judgment: I agree with the provisional view. A short feasibility discussion is worth having now; a formal architecture review is premature and would mostly produce design decisions the note deliberately leaves open ("Questions that determine whether this saves Joe time," §1–5). The note is already unusually honest — it separates documented Hermes capability from integration hypothesis and marks its own experiment as unauthorized — so a heavier review would add ceremony, not information.

One challenge worth keeping on the table: the manager/execution boundary risks duplicating what PM 0.19 already does. WORKFLOW.md's orchestrator already selects ready work, parks `needs-human` decisions, and continues independent work; the pm-019 intent says successors replace the orchestrator at context boundaries. The Hermes bot's distinct value is only the part PM structurally cannot do: stay alive *between* sessions and *initiate* the next one without Joe. If the trial shows the bot mostly relaying worker questions or re-deciding what the orchestrator would decide anyway, it is a second orchestrator, not a manager — the note's own §2 flags this. Judge the trial on transitions removed from Joe, not on management activity.

## Assumptions to test

Untested claims, all documentation-based per the note's "Research scope and confidence" section:

1. A Hermes bot can launch a Claude Code/Codex session that keeps a resumable identity — the note itself concedes "a process handle is not necessarily a resumable conversation identity" (§Connections to coding agents, H4/H5).
2. A launched session preserves PM/Ringer behavior, grants, and records rather than the bundled guides' generic recipes (same section).
3. Joe's reply can be routed back to the correct ticket and the exact live execution session (§4), including when stale.
4. Unattended operation actually works with Joe's transport — Desktop relaying requires Desktop open (H1).
5. One session-launch owner can be established between Hermes and PM succession without duplicate launches (§1); PM succession's own live-host behavior is itself still unproven per the pm-019 release evidence (restarts, a memory crash in earlier pilots).
6. Standing instructions confine a bot to its project — H2 says they don't; boundary enforcement is unsolved.

Assumptions 1–3 are the load-bearing ones; if any fails, the concept degrades to a scheduler that pings Joe, which he already effectively has.

## First observation

Smallest useful observation during today's trial (judgment): don't build anything. Have one Hermes bot, hand-configured, run **one lifecycle**: read real project state, start one execution session for one pre-agreed outcome, receive the handoff when it ends, and ask Joe one consolidated question mid-run. Watch three things: (a) did the session run with intended PM identity and records, (b) did Joe's answer reach the right place, (c) how many minutes of Joe's attention did the whole loop cost versus doing the transition himself. That directly tests assumptions 1–3 and matches the note's trial questions 2, 3, and 6 without needing the fleet, routines, or recovery machinery.

If even the launch step fails cleanly, that's a cheap, decisive result.

## Leave undecided

Everything the note already defers, plus a few worth naming explicitly:

- Backlog-choosing vs. bounded-package manager (§2) — decide after seeing one real handoff.
- Who writes shared records during execution, and hosting/sync of gitignored `_pm`/`.scratch` state (§3).
- Relationship to PM's session-succession beta — whether Hermes replaces it, drives it, or ignores it. Don't reconcile two unproven succession mechanisms on paper.
- Multi-project capacity control (§5) — irrelevant until one project works.
- Any skill, plugin change, or client pilot. The note requests none, and nothing in the trial requires one.
