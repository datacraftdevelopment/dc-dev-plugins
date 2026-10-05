# 01 · Runway

**Question:** does a script loop that runs AFK tickets on its own, and preps the next human-gated ticket ahead of time, cut how often Joe has to touch a ticket?

Design: `../../research/02-judgment-lookahead.md`.

## What it is

`runway.py` is one dependency-free Python file (Python 3.9+, git). It reads a pm-style tracker (`.scratch/<effort>/issues/NN-slug.md`) and adds one header line to it, `Gate: human`, for tickets that need Joe.

```bash
python3 runway.py --root <repo> status     # what's waiting on you, running, ready, blocked, done
python3 runway.py --root <repo> loop       # tick until only Joe's decisions remain
python3 runway.py --root <repo> tick       # one pass (for cron/launchd later)
python3 runway.py --root <repo> go 03 "note"
python3 runway.py --root <repo> no 03 "reason"     # "drop ..." resolves it instead
python3 runway.py --root <repo> setup     # Linear only: check access, create labels
```

Each tick:

1. Preps a decision packet for every `Gate: human` ticket whose blockers are all AFK work, and parks it as `needs-human`.
2. Runs the first ready, unblocked AFK (or approved) ticket in a git worktree on `runway/<effort>-<ticket>`, runs `check_cmd`, and merges into `runway/integration` on a pass. A failure gets one retry with the log, then parks as `needs-human`.

Your checkout and base branch are never touched. Merge `runway/integration` yourself. Everything is logged to `_pm/runway.log`.

## Config

Put `runway.json` in the target repo root (all keys optional). Set `"tracker": "linear"` to work a Linear project instead of `.scratch/`; see `linear_tracker.py` and `../03-linear/`.

```json
{
  "agent_cmd": "claude -p --permission-mode acceptEdits",
  "prep_cmd": "claude -p --permission-mode plan",
  "check_cmd": "npm test",
  "base_branch": "main",
  "integration_branch": "runway/integration",
  "notify_cmd": "osascript -e 'display notification \"{msg}\" with title \"Runway\"'"
}
```

The prompt is sent on stdin. **(unverified)** The default `claude -p` flags haven't been run against real Claude Code yet. A headless agent that needs to run tests will likely need `--allowedTools "Bash(npm test:*)"` or similar, and the plan-mode prep may need adjusting to print the packet cleanly. Tune these on the first real run.

## Run the offline demo

```bash
bash demo/demo.sh
```

It builds a throwaway git repo with five tickets (03 is `Gate: human`, 04 depends on 03), uses `demo/fake_agent.py` and `demo/fake_prep.py` instead of Claude, and runs the loop twice with a `go` between.

## Results

- **2026-10-05, offline demo (fake agent):** works as designed. 03's packet was prepped before any work started; 01, 02 and 05 ran and merged; the loop stopped with only 03 waiting. After `go 03`, 03 then 04 ran. Joe touches: 1 (the go) for 5 tickets. The failure path (check always fails) retried once, then parked the ticket as `needs-human` with the log and kept its branch.
- **2026-10-05, first real run (`claude -p`, Claude Code 2.1.285, Mac mini, practice repo `hours`):** worked first try with no config changes. The `--allowedTools` syntax and the read-only prep command both worked as written.
  - **Pass 1** (2m54s): both decision packets were prepped first (03 and 05), then 01, 02, 04 and 06 ran and merged. The loop stopped with only the two decisions waiting. Tests on `runway/integration`: 10 OK.
  - **Decisions:** Joe chose daily rounding for 03 and markdown only for 05, both on Projects decision cards.
  - **Pass 2:** 03 ran in 27s and 05 in 51s, both merged. Tests: 20 OK. `main` untouched.
  - **Totals:** 6/6 tickets done in about 4.5 min of agent time, with no failures or retries. Joe touched it 3 times: the 2 decisions, plus one typed "go" (see the first finding).
  - **Packet quality:** better than expected. Both packets computed real numbers from the sample (raw 9.87 h; 10.20 / 10.50 / 10.25 h billed per rule), recommended an option with reasons, and caught a planning gap in the tickets: ticket 04's report prints raw hours and no ticket wires 03's rounding into it. Confirmed after the run, when Acme showed 4.03 h raw against 4.25 h billed. That became ticket 07.
  - **Findings:**
    1. **A relayed approval doesn't count on the Mac.** Claude Code's auto-mode check on the Mac blocked `runway go 03` when Joe's card tap reached it through another Claude session, and treated it as an unrequested commit. Joe's own typed "go" in the thread cleared it. Design consequence for experiment 03: approval has to land in the tracker (a ticket edit, a Linear or GitHub status), which Runway reads on a schedule, with no Claude session relaying the go.
    2. **No token capture.** `runway.py` doesn't record usage from `claude -p`. Add it (e.g. `--output-format json`) before comparing against Hermes.
    3. **Leftover worktree.** Runway leaves its merge worktree at `sandbox/.runway-worktrees/_integration` between runs. It's harmless, but should be cleaned up or documented.
    4. **Ticket edits aren't tracked.** `.scratch/` is gitignored in the practice repo, so the needs-human edits and packets aren't in its git history. That's fine for practice. A real project should decide whether ticket history lives in git.
    5. **Credential guard still fires.** pm's credential-guard hook fired on two git commands during the session. Hooks keep working under Runway, which is good.
- **Next:** add ticket 07 (billed hours in the report) and token capture, then run on a real low-stakes project.

## Proposed first real run

1. `bash practice/setup.sh` creates a practice repo (`hours`, a tiny billing-summary tool) at `~/Agentic-Mini/_Tools/runway-practice`, with 6 tickets (2 gated) and a real `runway.json`. See `practice/README.md`.
2. Run `python3 runway.py --root ~/Agentic-Mini/_Tools/runway-practice loop` on your Mac and walk away.
3. Expected: 4 tickets merged and 2 packets waiting. Then `go` both and run `loop` again.
4. When you come back: `runway status`, read the packets, `go` them, `runway loop` again.
5. Record touches per ticket, packet lead time, parked failures and their causes, and tokens, in this README.

## Known limits (on purpose, for v1)

- One AFK ticket at a time. Parallelism is later; the bottleneck is Joe's touches, not throughput.
- No LLM diagnosis of failures. They park for Joe (or, later, hand off to Hermes or a Ringer task).
- No trigger. Joe starts `loop`; experiment 03 moves that to launchd/cron.
- Ticket edits stay in the working tree of the target repo; Runway doesn't commit tracker changes.
