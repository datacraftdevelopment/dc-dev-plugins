# Intent: pm 0.17 — local tracker by default, an inbox for loose asks, a named client face

Author: Joe (with Fable). Status: accepted. Date: 2026-09-12.
Completion: pending (ship-acceptance writes a verified docs/shipped/ link when delivered).
Source: discovery session 2026-09-12, prompted by "two task lists" in this repo and a
read of how a client repo actually runs its meeting → tasks → Basecamp loop. Pre-mortem
gate (Astra seat) same day: `.review-gate/2026-09-12-pm-017-intent/`; six findings,
five applied here, the size call held for Joe.

## Problem

pm's doctrine says work items live on the tracker and nowhere else, but nothing
in pm stands a tracker up. `pm-scaffold` never runs Matt's setup, so every repo
starts trackerless; the session Intent blocks in `_pm/sessions/` end up carrying
the queue, and the pre-0.8 `_pm/TASKS.md` lingers as a stale second list. This
repo is the example: `_pm/TASKS.md` last touched 2026-07-15, no
`docs/agents/issue-tracker.md`, no `.scratch/`.

Three kinds of item have no home at all. A loose idea from a client call
("maybe portal login someday") is not a ticket and not worth grilling into an
intent. A "waiting on the client for X" has nowhere to sit that `whats-next`
will read. And a pure question ("sold or donated?", "backfill or not?") whose
answer may produce no work, one ticket, or a change to existing work, has no
place either. TASKS.md's Backlog, Waiting-on and Questions buckets were quietly
doing that work, which is why the file survived the 0.8 reshape.

Client-facing tracking (Basecamp, in that client repo) is a third layer with its own
conventions, and pm has no seam for it. Today it lives entirely in one repo's
CLAUDE.md prose.

## Proposed outcome

Three tiers, and an item only ever moves down:

```
docs/intent/inbox.md      loose: one line per ask or idea, dated, sourced. No status.
docs/intent/<slug>.md     shaped: discovery ran, size call made.
.scratch/<slug>/issues/   the tracker: implementation tickets, and question tickets
                          (Matt's research / grilling types) whose answer is the work.
                          Never a loose idea.
```

- Every repo scaffolded by pm ≥ 0.17 has a local-markdown tracker
  (`docs/agents/issue-tracker.md` preset to `.scratch/`) and an empty inbox on
  day one. GitHub Issues stays a per-repo choice.
- **Waiting is a tracker state, not just a label.** A ticket that needs an
  answer carries `Waiting on:` (who, what, since when) **and** is set to the
  seam's existing `needs-human` status, so build-swarm's loop cannot select it.
  When the last wait is answered, the answer is appended under `## Comments`
  and the status is restored by hand. A question with no build behind it is a
  ticket of Matt's existing question types with `Waiting on:` set; its answer
  either resolves it with no work, spawns an implementation ticket, or comments
  on an existing one.
- `whats-next` reads the inbox as the ungroomed list, after open intents and
  the frontier, and can propose "discover this one." It lists waiting tickets
  under watch-outs, never as the pick-up. When the inbox holds more than
  twelve lines or any line older than four session opens, it names those
  lines and asks: keep, promote, merge, or retire.
- `discovery` takes the line out of the inbox when it writes the intent and
  cites it in Source.
- `stepping-away` offers to capture asks that surfaced this session, but
  **matches first**: against inbox lines, open intents, and tickets. A repeat
  adds its date and source to the existing item, never a new line. Retiring
  an inbox line deletes it from the live file; the reason goes in the session
  entry, which is the append-only record.
- If `docs/agents/client-face.md` exists, `stepping-away` follows the
  close-out procedure written there. pm never names a client-face tool or
  skill. The file's contract is small and tool-neutral: it must say how to
  find the close-out steps, what local evidence they consume (the ticket or
  commit, the `Client-ref:` line if any), and what to do for fully shipped,
  partly shipped, and ticketless changes. Until a real producer exists this is
  an **unintegrated optional hook**, and the intent says so rather than
  certifying client integration.
- `MIGRATION-0.17.md` gives the TASKS.md rubric: each item is dead (with the
  evidence), an inbox line, an intent, or a ticket, and each disposition names
  its destination. A repo that decided TASKS.md is its tracker (the client repo,
  2026-08-26) stays legitimate; the note says how pm reads it, not that it
  must move.
- This repo is migrated first: tracker file written, inbox created, the ten
  `_pm/TASKS.md` items mapped one by one, the file marked legacy.

## Acceptance

Local run 2026-09-13 against pm 0.17.0 installed from the marketplace: A1–A7 and A9 pass (A1 and the seam half of A4 by script; the rest by fresh-context agents following each 0.17.0 SKILL.md cold on throwaway fixtures — record in `.review-gate/2026-09-12-pm-017-intent/acceptance-local.md`). A8 is session two. The production run is the same checks on a real repo after `ship-acceptance`.

- [x] A1: Scaffold a throwaway project with `/pm:pm-scaffold` → `docs/agents/issue-tracker.md` (local) and `docs/intent/inbox.md` exist; no interactive tracker question was asked.
- [x] A2: Put two lines in that inbox and run `whats-next` → both appear under an "ungroomed" heading, after intents and the frontier, and the proposal offers to discover one.
- [x] A3: Run `discovery` on one of those lines and write its intent → the line is gone from the inbox and the intent's Source cites it.
- [x] A4: Under `.scratch/` add a `ready-for-agent` ticket, then mark it waiting on two questions → `whats-next` lists it under watch-outs, not as the pick-up, **and** build-swarm's `seam.py ready` does not return it. Answer one question → still excluded by both. Answer the second and restore the status → both offer it again.
- [x] A5: Add a question ticket with no build behind it → `whats-next` shows it as waiting, distinct from the inbox's ungroomed lines, and does not propose discovery on it.
- [x] A6: Run `stepping-away` twice in a scratch repo where the same client ask is raised in both sessions, once with a ticket already covering it → the inbox holds one line at most and that line, or the ticket, carries both dates; no second intent was proposed.
- [x] A7: Seed the inbox with fourteen lines, two dated before four earlier session files → `whats-next` names those lines and asks keep / promote / merge / retire; retire one → it is gone from the live file and the reason is in the session entry.
- [ ] A8: In this repo after migration → `_pm/TASKS.md` opens with a `> Legacy` line; a table in the session entry maps every one of its ten items to a destination path (inbox line, intent file, ticket file) or to a dated reason it is dead; every destination path exists; a cold `whats-next` in a fresh session surfaces each surviving item without reading TASKS.md or the migration session.
- [x] A9: With `docs/agents/client-face.md` present in a scratch repo and written to the contract above, run `stepping-away` after a fully shipped ticket, a partly shipped one, and a ticketless change → it quotes the matching step for each case and offers it; with the file absent it says nothing about a client face. (Manual check; no client tooling is exercised. This proves the hook, not client integration.)

## Affected users and systems

- `pm/template/` — two new files.
- `pm/commands/pm-scaffold.md`, `pm/skills/{whats-next,discovery,stepping-away}/SKILL.md`.
- `pm/WORKFLOW.md` (three-tier rule, waiting state, client-face layer), `pm/README.md` (Basecamp optional, lives in `_Tools/Basecamp`), `pm/MIGRATION-0.17.md` (new).
- `pm/.claude-plugin/plugin.json` version bump; marketplace update on both machines.
- This repo's `_pm/TASKS.md`, `docs/agents/`, `docs/intent/inbox.md`, `.scratch/`.
- Downstream: `_Tools/Basecamp` (being rebuilt in a parallel session) owes a
  `client-face.md` written to the contract above; that session owns it.
  The client repo is untouched; a later session there reviews pm 0.17 and decides
  whether to migrate.

## Constraints

- pm stays two layers plus a pace rule plus a hook. The inbox is a file in
  `docs/`, not a state store: nothing tracks progress on it, and a line leaves
  only by becoming an intent, merging into an existing item, or being retired
  with a reason in the session entry.
- `.scratch/` layout is Matt's convention unchanged, and build-swarm's
  `seam.py` is not edited. `Waiting on:` and `Client-ref:` are descriptive
  header lines; the seam sees only its existing `Status:`. That is why waiting
  must also set `needs-human`.
- Client-face coupling is one file name. No Basecamp skill, id, or CLI appears
  anywhere in pm.
- The inbox lives in `docs/`, so it is client-readable; write it in client-safe words.
- Derived trees (`fm-rcc`, public `dc-plugins`, `tc-plugins`) are re-cut, never hand-edited.

## Open questions

- Should `discovery`'s intent template gain a `Status: idea` value, or is the
  inbox line the only pre-intent state? (Lean: inbox only; a stub file per idea
  is the TASKS.md rot in a new shape.)
- Cross-effort blocking edges (`Blocked by:` pointing into another
  `.scratch/` effort). The client repo needs them; Matt's convention doesn't have them.
  Park until the client repo's review session.
- A tracker-neutral `meeting-pass` skill (transcript → capture with verified
  root causes → inbox or tickets, client-face steps from the file if present)
  is the biggest lesson from the client repo and the least proven elsewhere. Own intent,
  after this ships. The match-before-append rule above is written in
  `stepping-away` so it does not wait on that skill.
- Does `pm-scaffold` also drop the local-tracker file into an existing repo
  (the in-place mode), and does it ever overwrite one that's there? (Lean: write
  only if absent.)
- Inbox review thresholds (twelve lines, four session opens) are a first guess;
  tune after a month.

## Size call

Size: **two sessions** (Joe, 2026-09-12, after the pre-mortem). Session one: the pm
changes, A1–A7 and A9 run on a scratch project. Session two: this repo's
migration, A8. Plan mode or direct build with this intent as the brief. Before
the gate the call was one session; the seat showed the behavioral decisions
were unsettled, they are now written above, and the check list grew to nine.

Map Notes for charting (not charted): Taste for this effort: the inbox line format; what `whats-next` calls the ungroomed list; wording of the `> Legacy` line; the inbox review thresholds.
