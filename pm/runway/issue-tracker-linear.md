# Issue tracker: Linear

Issues for this repo live in Linear, team **{{TEAM}}**, project **{{PROJECT}}**.
Use the Linear MCP tools (the Linear connector). If they aren't available, stop and
tell Joe to reconnect Linear (claude.ai Settings, Connectors); don't fall back to
local files.

Runway (SoftwareFactory) works this project's queue on a schedule, so the labels
below are load-bearing: they decide what runs without Joe.

## Conventions

- **Create an issue**: in team {{TEAM}}, project {{PROJECT}}. Markdown body.
- **Read an issue**: fetch it with its comments and labels.
- **List issues**: filter by project {{PROJECT}} plus the labels or state you need.
- **Comment**: add a comment to the issue.
- **Labels**: add or remove by name. Create a missing `wayfinder:*` label on the team.
- **Close**: move to `Done` (or `Canceled` for won't-do) with a comment.

## Triage labels Runway reads

| Label | Meaning | Who sets it |
|---|---|---|
| `ready-for-agent` | AFK build work. Runway runs it in a worktree and merges to `runway/integration`. | `/to-tickets` (its default) |
| `ready-for-human` | Build work that needs Joe's call first. Runway preps a decision packet as a comment. | Whoever plans the ticket |
| `go` | Joe approved a `ready-for-human` ticket. | Joe (or a comment starting `go`) |
| `needs-human` | Parked, waiting on Joe. Runway never picks it. | Runway |

When publishing build tickets, sort each one into a bucket before labelling it.
Precedence runs top to bottom: the first bucket that fits wins.

| Bucket | Looks like | Label |
|---|---|---|
| **One-way door** | Migrations or transforms on live data, deletes, anything public or production-facing, spend, credentials, client data, an architecture choice that would take more than a session to unwind. | `ready-for-human` |
| **User challenge** | The ticket's plan contradicts something Joe already said (in the spec, the conversation or an earlier decision). | `ready-for-human`, and quote what he said |
| **Taste** | Anything a user sees or feels: flow order, wording, defaults a client will notice, what ships first, what "done enough" means. | `ready-for-human` |
| **Technical** | Library or pattern inside the chosen stack, file layout, naming, error handling, test seams, endpoint shape: anything the codebase or the spec can settle. | `ready-for-agent` |

Unsure between technical and taste: `ready-for-agent`, and name the assumption in
the body so the finish review can catch it. Unsure whether something is
reversible: treat it as a door. For a `ready-for-human` ticket, say why in the
body and what "go" will do. Never put both labels on one ticket.

**Size floor.** Work under about an hour of solo effort is not its own ticket.
Fold it into the ticket it serves.

## Reviewing decisions with Joe

When Joe asks to review what's waiting on him, list the open `ready-for-human`
issues labelled `needs-human` and walk through each one's latest Runway
decision packet (the comment starting `🛫 runway`). Then:

- Post `go <choice and any notes>` as a comment **only after Joe has said go
  on that specific ticket in this conversation**, with his choice. Never
  approve on your own judgment, a recommendation, or a general "looks fine".
  The connector writes as Joe, so Runway can't tell the difference.
- Post `drop` only when Joe says to drop that ticket.
- Don't touch the labels; Runway manages `go` and `needs-human` itself.

## When a skill says "publish to the issue tracker"

Create a Linear issue in team {{TEAM}}, project {{PROJECT}}.

## When a skill says "publish a spec"

The spec is a file in the repo: write it to `docs/specs/<slug>.md` (kebab-case, a few words) and get it onto
the base branch before its tickets are labelled for Runway, so every worker reads it from its own checkout.
Then `/to-spec` publishes the tracker entry as an issue: first line `Spec: docs/specs/<slug>.md`, then a copy
of the text. A later change goes into the file first, then re-paste it into the issue.

Label the issue `spec`, and never `ready-for-agent` or `ready-for-human`,
whatever the skill says about triage. Runway skips any issue labelled `spec`, and any issue that has child issues,
so the spec doesn't run as a ticket alongside its own tickets. `/to-tickets` then publishes the build tickets as
child issues of the spec, and those carry the triage labels. Each ticket's description names its spec in a
header line, `Spec: docs/specs/<slug>.md`.

## When a skill says "fetch the relevant ticket"

Fetch the Linear issue by its identifier (e.g. `{{TEAM}}-12`) or URL, with comments.
If it has a `Spec:` line, read that file from the checkout too: it is the spec the ticket builds.

## Blocking

Use Linear's native **blocks** relation (Linear shows it as "Blocked by" on the
blocked issue). Publish blockers first so the relation can point at real issues.
Runway treats an issue as unblocked when every blocker is Done or Canceled.

**Conflict screen.** Two tickets that touch the same files (lockfiles, generated
code, migrations, schema and config registries count), write the same database,
or need the same port or dev server must not run side by side. Give them a
blocks relation in the order they should land, even when neither needs the
other's output.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one issue; **children** are sub-issues.

- **Map**: an issue in project {{PROJECT}} labelled `wayfinder:map`, holding the
  Destination / Notes / Decisions-so-far / Not-yet-specified / Out-of-scope body.
- **Child ticket**: a sub-issue of the map (set its parent), labelled
  `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Wayfinder
  tickets never get `ready-for-agent` or `ready-for-human`: they're decisions,
  not builds, and Runway ignores them.
- **Blocking**: the native blocks relation, as above.
- **Frontier query**: the map's open sub-issues with no open blocker and no assignee; lowest number first.
- **Claim**: assign the issue to Joe (the session's first write).
- **Resolve**: comment the answer, move to Done, then add a context pointer
  (gist + link) to the map's Decisions-so-far.

When the map is clear, `/to-spec` then `/to-tickets` turn it into the build
tickets Runway works.
