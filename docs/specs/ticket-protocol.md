# Spec: one ticket protocol behind thin GitHub and Linear adapters

Tracker entry: #39 (tickets #40-#43, #45). Moved here from the issue body on 2026-10-10.

Candidate 1 of the 2026-10-09 Runway architecture audit. Interface settled with Joe; technical questions went through fast grill (Astra seat via Ringer, two rounds; every disagreement was taken as Astra's alternative, so no splits).

## Problem

`github_tracker.py` (GitHubTicket, GitHubTracker.sync) and `linear_tracker.py` (LinearTicket, LinearTracker.sync) each carry their own copy of Runway's ticket protocol: gate, status, claimed_by, packet, Joe's replies, go/drop parsing, park/approve/decline wording, the trust rule, `_log_once`. The copies have drifted (a `go` note is kept on GitHub and dropped on Linear; only Linear's park message says "comment go") and fixes land twice (#11, #13; #22 is the same bug in both).

## Interface

**One ticket protocol module owns every rule.** Each tracker adapter gives facts and writes only (Joe, 2026-10-09).

Adapter facts:
- id, num, url, title, body, labels, has-sub-issues, blocker ids (native, else GitHub's `Blocked by:` line; out-of-queue blockers still arrive as stubs that gate)
- lifecycle: open, started, closed-completed, closed-canceled. The adapter normalizes its own "started" (GitHub: has an assignee; Linear: a started workflow state) and "closed" (Linear's duplicate counts as completed)
- assignee logins (GitHub release needs them to unassign)
- comments, oldest first: body, timestamp, trusted flag, author login and association

Adapter writes: comment, add/remove labels, move to ready / claimed / resolved / canceled, close-with-comment. Workflow state names, the `gh` / GraphQL transport, pagination, retries and the timed-out-write "landed" check stay in the adapter. Label roles (`agent_label`, `human_label`, `approve_label`, `needs_human_label`, `spec_label`) are protocol config.

## Rulings

- **Drift settles on the forgiving version** (Joe): `go <note>` keeps the note on both trackers; both park messages say "comment `go` to retry"; the trust rule lives in the protocol and covers ticket text, packet, claimed_by and replies, with Linear marking every comment trusted (private workspace); ignored strangers' go/drop stay logged once. Kept: an approved gate wins over a latest `drop`.
- **Writes:** claim stays stamp-first. Resolve and drop are one close-with-comment call (GitHub one `gh issue close --comment`, Linear state then comment); the landed check for a timed-out close confirms the close, not only the comment.
- **Two comment histories:** ticket text and recent replies use the latest 50 comments; claimed_by pages back to the start of the current claim cycle, because the earliest stamp wins and a window can drop the real owner. Linear reads `first: 25` today.
- **Partial failures:** Linear's park does state, needs-human and go removal in one issueUpdate; approve and park become resumable; release stays state-first and keeps its go label.
- **Engine:** a ticket exposes `commit_ref` and `pr_ref` (PR bodies say "Refs", never "Closes"); the tracker reports the sign-ins it needs, merged with the engine's own. pm's markdown `Ticket` stays outside the protocol with the same interface.
- **Tests:** protocol rules against an in-memory adapter; keep the adapter-to-engine scenarios; change only assertions a ticket changes on purpose.

## Tickets

Sub-issues of #39. All wait for #7 (engine moves into pm); line references are from main at a79ff06, so re-check them against #7's tree. #22 moves behind the extraction ticket. Related: #28 (trackers can create a ticket) adds `create` to the protocol if this lands first; #37/#38 call the same `mark_*` writes.
