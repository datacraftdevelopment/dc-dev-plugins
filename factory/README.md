# SoftwareFactory

Research and experiments for taking Joe's PM Dev workflow from "one session, Joe in the loop" to a software factory: triggers start the agent work, routine tickets run on their own, and the next decision that needs Joe is prepped and waiting so he only has to say go.

## Layout

| Path | What's in it |
|---|---|
| `research/` | Notes. Start with `01-pm-dev-vs-factory.md`. |
| `research/software-factory-notes.md` | Joe's original landscape notes (moved here, unchanged). |
| `experiments/` | One folder per experiment, numbered. Each has a README with the question, how to run it, and results. |
| `experiments/01-runway/` | The first experiment: a judgment-aware task runner for a pm-style tracker. |
| `decisions.md` | Short log of choices made in this repo and why. |

## Reading order

1. `research/01-pm-dev-vs-factory.md`: what a factory is, and what PM Dev already has versus what it's missing.
2. `research/02-judgment-lookahead.md`: the design for the "prep the next judgment" bottleneck.
3. `research/03-sandcastle.md`: what Sandcastle is, verified details, and where it fits.
4. `research/04-projects-as-factory.md`: whether Claude Code Projects already is the factory, and where the gap is.
5. `research/05-projects-quirks.md`: everything that went sideways running this from a Projects thread.
6. `experiments/01-runway/README.md`: the simplest thing to spin up first.
