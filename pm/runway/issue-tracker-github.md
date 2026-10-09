# Issue tracker: GitHub

Issues for this repo live in GitHub Issues, repo **{{REPO}}**. Use the `gh` CLI.
If `gh` isn't signed in, stop and tell Joe to run `gh auth login`; don't fall
back to local files.

Runway works this repo's queue on a schedule, so the labels below are
load-bearing: they decide what runs without Joe.

**Public repos.** If this repo is public, its issues and comments are public too.
No client names, credentials or NDA material go into an issue or a comment.
`runway setup` warns when the repo is public.

## Conventions

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Make an issue a sub-issue of a parent**: `gh issue create --parent <parent> ...`, or `gh issue edit <parent> --add-sub-issue <child>` afterwards (`gh` 2.94+). Older `gh`: `gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>` (database id, as in **Blocking** below). Without sub-issues, put `Part of #<parent>` at the top of the child body.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh api --paginate 'repos/{owner}/{repo}/pulls?state=open' --jq '.[] | select(.author_association | IN("OWNER","MEMBER","COLLABORATOR") | not) | {number, title, author: .user.login, author_association, labels: [.labels[].name]}'`.
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "publish a spec"

`/to-spec` publishes the spec as an issue. Label it `spec`, and never `ready-for-agent` or `ready-for-human`,
whatever the skill says about triage. Runway skips any issue labelled `spec`, and any issue that has sub-issues,
so the spec doesn't run as a ticket alongside its own tickets. `/to-tickets` then publishes the build tickets as
sub-issues of the spec (see **Make an issue a sub-issue of a parent**), and those carry the triage labels.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (see **Make an issue a sub-issue of a parent**). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.

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
issues labelled `needs-human` (`gh issue list --label needs-human`) and walk
through each one's latest Runway decision packet (the comment starting
`🛫 runway`). Then:

- Post `go <choice and any notes>` as a comment **only after Joe has said go
  on that specific ticket in this conversation**, with his choice. Never
  approve on your own judgment, a recommendation, or a general "looks fine".
  `gh` writes as Joe's account, so Runway can't tell the difference.
- Post `drop` only when Joe says to drop that ticket.
- Don't touch the labels; Runway manages `go` and `needs-human` itself.
- Runway only honors a `go` or `drop` comment from a trusted author (the repo's
  OWNER, MEMBER or COLLABORATOR). A stranger's comment is ignored and logged.

## Blocking and the conflict screen

Use GitHub's native issue dependencies ("blocked by"), as in **Wayfinding
operations** above; without them, a `Blocked by: #n, #m` line at the top of the
body. Runway treats an issue as unblocked when every blocker is closed.

**Conflict screen.** Two tickets that touch the same files (lockfiles, generated
code, migrations, schema and config registries count), write the same database,
or need the same port or dev server must not run side by side. Block one on the
other in the order they should land, even when neither needs the other's output.

## Two header lines pm reads

On GitHub these are lines at the top of the issue body.

- **`Waiting on:`**: who, what, since when. Carries the `needs-human` label too.
- **`Client-ref:`**: the client-facing item this ticket maps to, if the repo has
  a `docs/agents/client-face.md`. Descriptive only; never a client's name in a public repo.
