# factory

The installable part of the software factory. The research, decisions and
experiments that produced it are one folder up in `factory/` and don't ship.

| Piece | What it is |
|---|---|
| `skills/runway/` | Set up a repo for Runway, plan and label its tickets, run and watch the loop, answer decisions, retro. |
| `runway/runway.py`, `runway/linear_tracker.py` | The engine. Python 3.9+ and git only. |
| `runway/setup.sh` | Points a repo at a Linear project: `docs/agents/issue-tracker.md`, `runway.json`, CLAUDE.md section. |
| `runway/schedule.sh` | Installs, fires, shows or removes the launchd job that runs the loop. |
| `runway/issue-tracker-linear.md` | The tracker file `setup.sh` stamps: labels, the gating rule, the conflict screen. |
| `runway/worker-env.md` | Template for a repo's `docs/agents/worker-env.md`, which every ticket run reads first. |

Install alongside `sdlc` (the credential guard and gates) and Matt Pocock's
skills (`/to-spec`, `/to-tickets`, `/tdd`, `/code-review`, `/pr`, `/retro`).

```
/plugin install factory@dc-dev-plugins
```

Tests live with the experiments: `bash factory/scripts/check.sh` from the
marketplace root runs them all. The old paths
`factory/experiments/01-runway/runway.py` and
`factory/experiments/03-linear/schedule.sh` forward here, so LaunchAgents
installed before the move keep working.
