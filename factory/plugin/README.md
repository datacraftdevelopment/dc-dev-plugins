# factory

The installable part of the software factory. The research, decisions and
experiments that produced it are one folder up in `factory/` and don't ship.

| Piece | What it is |
|---|---|
| `skills/runway/` | Set up a repo for Runway, plan and label its tickets, run and watch the loop, answer decisions, retro. |
| `skills/runway/playbook.md` | How a repo runs Matt Pocock's skills (Wayfinder, grilling, `/to-spec`, `/to-tickets`) with Runway, and how to set one up. The runway skill reads it when setting up a repo. |
| `runway/runway.py`, `runway/linear_tracker.py`, `runway/github_tracker.py` | The engine and its two tracker adapters. Python 3.9+ and git only. |
| `runway/setup.sh` | Points a repo at a Linear project or a GitHub repo (`--github`): `docs/agents/issue-tracker.md`, `runway.json`, CLAUDE.md section. |
| `runway/schedule.sh` | Installs, fires, shows or removes the launchd job that runs the loop. |
| `runway/issue-tracker-linear.md`, `runway/issue-tracker-github.md` | The tracker file `setup.sh` stamps for each tracker: labels, the gating rule, the conflict screen. |
| `runway/runway.json.template`, `runway/runway.json.github.template` | The `runway.json` `setup.sh` writes for Linear and for GitHub. |
| `runway/worker-env.md` | Template for a repo's `docs/agents/worker-env.md`, which every ticket run reads first. |

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

Install alongside `pm` (the credential guard and gates) and Matt Pocock's
skills (`/to-spec`, `/to-tickets`, `/tdd`, `/code-review`, `/pr`, `/retro`).

```
/plugin install factory@dc-dev-plugins
```

Tests live with the experiments: `bash factory/scripts/check.sh` from the
marketplace root runs them all. The old paths
`factory/experiments/01-runway/runway.py` and
`factory/experiments/03-linear/schedule.sh` forward here, so LaunchAgents
installed before the move keep working.

## Menu bar app

When `tick`, `loop` or `finish` starts on a Mac with `/Applications/Runway.app` installed (`bash factory/app/make-app.sh --install`) and the app isn't running, Runway opens it in the background first, so a run started by launchd or by Claude always shows in the menu bar. Set `RUNWAY_NO_APP=1` to skip this; test runs skip it on their own.
