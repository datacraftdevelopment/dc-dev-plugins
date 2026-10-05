# SoftwareFactory

Research repo plus small experiments. Not a product.

- Notes go in `research/`, numbered. Keep each one about a single question and mark anything not verified first-hand as **(unverified)**; the tooling changes weekly.
- Experiments go in `experiments/NN-name/` with a README stating the question, how to run, and results. Record results even when an experiment fails.
- Experiments target pm's local markdown tracker (`.scratch/<effort>/issues/NN-slug.md`) so they work on real PM Dev projects without migration.
- Never run an experiment against a client repo's base branch. Runners write to an integration branch; Joe merges.
- Log choices in `decisions.md`, one dated line each with the why.
