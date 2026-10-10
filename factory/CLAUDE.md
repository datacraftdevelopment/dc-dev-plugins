# SoftwareFactory

Research repo plus small experiments. Nothing here ships. The Runway engine and the `runway` skill live in pm (`../pm/runway/`, `../pm/skills/runway/`); edit the engine there, not in `experiments/`.

The local oversight pilot lives in `scripts/observe.py`; operation, evidence and
merge gates are in `scripts/OBSERVER.md`. It reads Runway records and writes a
deduplicated local event queue without model calls. It does not wake a conversation
or merge anything. Treat ticket acceptance evidence and fresh review provenance,
not a successful process exit, as the completion contract.

- Notes go in `research/`, numbered. Keep each one about a single question and mark anything not verified first-hand as **(unverified)**; the tooling changes weekly.
- Experiments go in `experiments/NN-name/` with a README stating the question, how to run, and results. Record results even when an experiment fails.
- Experiments target pm's local markdown tracker (`.scratch/<effort>/issues/NN-slug.md`) so they work on real PM Dev projects without migration.
- Never run an experiment against a client repo's base branch. Runners write to an integration branch; Joe merges.
- Log choices in `decisions.md`, one dated line each with the why.
