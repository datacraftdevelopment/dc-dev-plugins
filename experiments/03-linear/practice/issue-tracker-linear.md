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

When publishing build tickets, apply `ready-for-agent` by default. Apply
`ready-for-human` **instead** when the ticket changes something a client will
notice, picks between product options, or is hard to undo. Say why in the body,
and say what "go" will do. Never put both labels on one ticket.

## When a skill says "publish to the issue tracker"

Create a Linear issue in team {{TEAM}}, project {{PROJECT}}.

## When a skill says "fetch the relevant ticket"

Fetch the Linear issue by its identifier (e.g. `{{TEAM}}-12`) or URL, with comments.

## Blocking

Use Linear's native **blocks** relation (Linear shows it as "Blocked by" on the
blocked issue). Publish blockers first so the relation can point at real issues.
Runway treats an issue as unblocked when every blocker is Done or Canceled.

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
