# PM 0.21 orchestrated runs

`orchestrate` now runs on a context budget: an orchestrated run starts in a fresh
session from a written brief, reads Ringer results by path, and rotates at a wave
boundary past about 150K tokens. Two field runs (Hermes pilot 2, Marvel) spent
more on the orchestrator re-reading its own context than on the workers.

Astra or Fable may lead an orchestrated run as a manager-only seat; they are
still never implementation workers and review still goes through Ringer. This
amends pm-020. Standing seat preferences let an unattended run pick worker models
without asking.

Also new in the skill: acceptance tests written and baselined before dispatch, a
per-repo `docs/agents/worker-env.md` written on the first orchestrated run, an
integration branch with one commit per verified ticket, orchestrator-regenerated
artifacts, `needs-human` tickets closed only by Joe, unanswered decisions parked
rather than dropped, and a fixed end-of-run report with seat usage. Sharpened:
CPU load before fan-out, focused worker tests with one central full suite per
wave, a size floor for delegation, one wave per Ringer run.

The default changed back the same day. Orchestration is opt-in; the default loop
is one session per outcome (`whats-next` → work → `stepping-away`), and
`stepping-away` now offers to open a fresh session for the next ready work. The
week orchestration was the default, Claude Code usage went 2.6x on doubled calls.

New skill `sibling-sessions`: two or three independent ready tickets each run in
their own ordinary session, through their own merge, with nobody watching the
others. It is the default way to parallelize, ahead of `orchestrate`'s subagents.

No new scripts, config files or tools. Intent: `docs/intent/pm-021-orchestrated-runs.md`.
Source and generated-package regressions pin the rules.
