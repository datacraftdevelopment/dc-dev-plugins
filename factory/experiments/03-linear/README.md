# 03 · Linear as the tracker

**Question:** with Linear as the tracker and Runway on a schedule, can Joe plan a small project in Claude Code, walk away, and only touch it to answer decision packets from Linear (phone included)?

This replaces the earlier "projects-floor" plan for 03. Projects threads stay the place to talk; Linear is where tickets and approvals live, because a go has to land in the tracker (see `decisions.md`).

## How the pieces connect

```
Claude Code session in the repo              Linear (team / project)                 Mac mini, every 10 min
/wayfinder  -> decision tickets (wayfinder:*)  ── ignored by Runway ──
/to-spec, /to-tickets -> build tickets ──────► ready-for-agent ──────────────► runway loop: run, check, merge
                     (judgment calls) ───────► ready-for-human ─► packet comment ◄── prep (read-only)
                                               Joe: comment "go …" ──────────► next tick runs it
```

- **Wayfinder and /to-tickets write to Linear** because the repo's `docs/agents/issue-tracker.md` says so. That file is what `/setup-matt-pocock-skills` writes; `practice/setup.sh` writes a Linear version directly so there's nothing to answer. The skills use the **Linear connector** in Claude Code.
- **Runway reads Linear** through `01-runway/linear_tracker.py` with a **personal API key** (a scheduled script can't use the connector's sign-in).
- **Wayfinder makes decision tickets, not build tickets.** Its own rule: a map is only for work with interdependent unknowns, and it "plans, doesn't do". Runway ignores `wayfinder:*` tickets. The build tickets Runway runs come from `/to-tickets`, which labels them `ready-for-agent` by default. For a small project, skip Wayfinder and go straight to `/to-spec` → `/to-tickets`.

## Label and state mapping

| Runway (markdown) | Linear |
|---|---|
| `Gate: auto` | label `ready-for-agent` |
| `Gate: human` | label `ready-for-human` |
| `Gate: approved` | `ready-for-human` + label `go` |
| `Status: needs-human` | label `needs-human` (state goes back to Todo) |
| `Status: claimed` | state `In Progress` |
| `Status: resolved` | state `Done` (or `Canceled`) |
| `Blocked by: NN` | native "blocks" relation |
| decision packet section | a comment starting `🛫 runway` |
| `runway go NN "note"` | Joe comments `go <note>` (or adds the `go` label) |
| `runway no NN "drop"` | Joe comments `drop` |

Issues without either label (wayfinder tickets, Joe's own notes) are never run, but still count as blockers. Joe's comments are passed to the agent as part of the ticket, so a choice written after `go` reaches it.

## Kick off the factory on a small project

One-time:

1. **Reconnect Linear** on claude.ai (Settings → Connectors). In Claude Code on the Mac, `/mcp` should then list Linear. **(unverified)** that claude.ai connectors reach the local CLI on this setup; if not, `claude mcp add --transport http linear https://mcp.linear.app/mcp`.
2. **Make a Linear API key** for Runway (Linear → Settings → Security & access → Personal API keys) and put it in the keychain:
   `security add-generic-password -s runway-linear -a "$USER" -w` (paste the key at the prompt).

Per project:

3. In Linear, create a **project** for it in your team (note the team key, e.g. `DC`).
4. Point a repo at it (creates a tiny Python repo if the path doesn't exist):
   ```bash
   cd ~/Agentic-Mini/_Tools/SoftwareFactory
   bash experiments/03-linear/practice/setup.sh sandbox/linear-practice DC "Runway practice"
   python3 experiments/01-runway/runway.py --root sandbox/linear-practice setup   # checks key/team/project, creates labels
   ```
5. **Plan it.** `cd sandbox/linear-practice && claude`, describe the project, then `/to-spec` and `/to-tickets`. Approve the breakdown; the tickets land in Linear. Flag anything that needs your judgment as `ready-for-human` (the tracker doc tells the skill when). Use `/wayfinder` first only if there are open questions that depend on each other.
6. **Start the schedule:**
   ```bash
   bash experiments/03-linear/schedule.sh install sandbox/linear-practice 10
   ```
   It runs `runway loop` now and every 10 minutes. `schedule.sh status <repo>` shows the last log lines.
7. **Answer from Linear.** Packets arrive as comments on `ready-for-human` issues (and a Mac notification). Comment `go` plus any choice; the next run picks it up. Failed runs park with `needs-human` and the log in a comment.
8. **Merge** `runway/integration` into `main` when you're happy. Runway never touches `main`.

Stop it with `schedule.sh uninstall <repo>`.

## Tests

`test/test_linear.sh` runs the whole Linear path offline against `test/fake_linear.py` (an in-memory stand-in that serves the adapter's exact GraphQL) with fake agents: 6 issues, one gated, one Wayfinder ticket, one blocked by it.

The adapter's 7 GraphQL operations were also validated against Linear's published SDK schema (`linear/linear`, `packages/sdk/src/schema.graphql`, fetched 2026-10-05). Neither replaces a run against real Linear.

## Results

- **2026-10-05, offline (fake Linear, fake agent), in the cloud container and on the Mac's folder VM:** `setup` created the missing labels. Loop 1 prepped the gated issue's packet as a comment, ran and merged the two AFK issues, and stopped with the gated issue waiting and two blocked (one behind the gate, one behind a Wayfinder ticket, which Runway left alone). A Joe comment `go greet() please` was picked up by the next loop, which ran the gated issue (the agent saw the note) and then its dependent. The markdown tracker path still behaves as in experiment 01.
- **2026-10-05, real Linear (DataCraft team `DAT`, project "Runway practice", real `claude -p` on the Mac mini):** 4 tickets planned through the Linear connector (3 `ready-for-agent`, 1 `ready-for-human` for the split-bill rounding rule). Works end to end.
  - **Packet:** DAT-7's packet was posted as a Linear comment before any build started. It recommended "first" (leftover cents to the first people) with worked numbers ($50.15 / 3 → 16.72, 16.72, 16.71) and said a bare "go" would mean "first".
  - **Joe's touch:** one threaded reply, `go`, in Linear. The next pass picked it up and posted "Approved". Joe asked whether he should also move the label to `ready-for-agent`; no, labels are Runway's job. Worth saying on the packet itself.
  - **Run:** DAT-5 → DAT-6 → DAT-7 → DAT-8 in about 3 minutes, all Done in Linear, each merged to `runway/integration`. 28 tests pass in a clean clone of that branch; `main` untouched.
  - **Touches:** 1 for 4 tickets (the go), plus the typed "run it" in the Projects thread that auto mode needs before a Claude session may start the loop.
  - **Schedule:** the launchd job loaded, its first run exited 0 and read Linear with the keychain key. There was nothing to build, so `claude -p` under launchd is still unproven.
  - **Bugs found and fixed:** (1) Linear rejected the queries as too complex (18,865 vs a 10,000 limit), because nested page sizes multiply; capped them. (2) `setup.sh` broke on a relative path for a new repo. (3) Two sandbox repos shared one `_integration` merge worktree, so DAT-5's merge ran in the wrong repo and was parked; `worktree_dir` now defaults to `../.runway-worktrees/{repo}`. (4) Linear's `duplicate` state type now counts as done.

## Known gaps

- **(unverified)** launchd jobs reaching `claude -p` auth. The keychain works from launchd (first scheduled run); `claude -p` gets proven the first time a ticket is ready when the job fires.
- Starting the loop from a Claude session needs Joe's own typed request (auto mode blocks unattended agent runs otherwise). The launchd job doesn't go through Claude Code, so once it's installed this stops mattering.
- The older `sandbox/runway-practice` repo still has its merge worktree at the old shared path; remove it (`git worktree prune` after deleting `../.runway-worktrees/_integration`) before running Runway there again.
- Anyone in the Linear workspace can comment `go`. Fine solo; with clients in the workspace, restrict to Joe's user id.
- One AFK ticket at a time, as in 01. No token capture yet.
