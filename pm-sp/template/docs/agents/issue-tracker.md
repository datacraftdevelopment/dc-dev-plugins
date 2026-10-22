# Issue tracker: Local Markdown

Preset by the pm-sp plugin: local markdown is the default tracker. In
pm-sp it is used only by `wayfinder`, for foggy efforts;
build work lives in design docs and plans, not tickets.
Switch to GitHub Issues by copying pm-sp's
`templates/issue-tracker-github.md` over this file. The conventions below
are Matt Pocock's local-markdown tracker, unchanged, plus one descriptive
header line pm-sp reads.

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

**Ticket granularity:** a ticket represents a meaningful outcome, not every
implementation step. Scaffolding, file edits, tests, repairs and subagent
assignments stay under their parent ticket as a compact work graph and evidence.
Create another ticket when work needs a separately useful outcome, owner,
acceptance boundary or durable unresolved dependency. Do not create tiny tickets
just to use a build engine. A small direct request may be handled without one.

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` — never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` — the Notes / Decisions-so-far / Fog body.
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.

## One header line pm-sp reads

- **`Waiting on:`** — who, what, since when. A wayfinder ticket that needs
  the user's answer carries it; `whats-next` lists it under *Waiting on you*.

Loose ideas never go here; they go to `docs/inbox.md`.
