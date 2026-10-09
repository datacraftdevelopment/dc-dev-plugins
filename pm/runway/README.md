# Runway (the engine, inside pm)

Runway's engine and setup scripts. They moved here from the old `factory` plugin
(2026-10-09, pm 0.26.0); the research, decisions and experiments are in `factory/`
and don't ship. The `runway` skill is `pm/skills/runway/`.

| Piece | What it is |
|---|---|
| `runway.py`, `linear_tracker.py`, `github_tracker.py` | The engine and its two tracker adapters. Python 3.9+ and git only. |
| `setup.sh` | Points a repo at a Linear project or a GitHub repo (`--github`): `docs/agents/issue-tracker.md`, `runway.json`, CLAUDE.md section. |
| `schedule.sh` | Installs, fires, shows or removes the launchd job that runs the loop. |
| `issue-tracker-linear.md`, `issue-tracker-github.md` | The tracker file `setup.sh` stamps for each tracker: labels, the gating rule, the conflict screen. |
| `runway.json.template`, `runway.json.github.template` | The `runway.json` `setup.sh` writes for Linear and for GitHub. |
| `worker-env.md` | Template for a repo's `docs/agents/worker-env.md`, which every ticket run reads first. |

Runway works either tracker, one per repo, chosen in `runway.json`.

Ringer is optional here. Only the review panel (`"review": "panel"`) uses it; without
Ringer, Runway falls back to the single Claude review. See the runway skill.

## Pause, quiet time, harnesses, claims

- **Pause.** `runway pause --for 1h` (or `--until <ISO>`) lets a running ticket finish and starts
  nothing new. `--stop-now` also stops running agents, the review panel included; stopped tickets go
  back to ready. `runway resume` lifts it. It is machine-wide (`~/.runway/pause`).
- **Quiet-time rules.** `~/.runway/machine.json` sets quiet hours, idle-only, not-on-battery and
  `max_agents` for this Mac. `runway machine` shows whether a tick would run.
- **Harnesses.** `runway.json` `"harness"` picks the default agent CLI (`claude` or a key of
  `"harnesses"`); a ticket overrides it with a `harness:<name>` label or `Harness:` header.
- **Claims.** A claimed ticket carries the machine name (`Claimed-by:` header, or a Linear claim
  comment). It clears when the ticket is parked, resolved, approved, declined or put back to ready.

The runway skill has the full detail.
