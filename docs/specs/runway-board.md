# Spec: the Runway window is a ticket board

Joe, 2026-10-12: the side panel looks great, but the main window is one big panel and isn't exciting. Asked whether
it should be Kanban-style; liked the mock ("this is looking much better").

Mock: https://claude.ai/artifact/WPh6cuQZuXUtU5ikmkkZhz (private to Joe).

Built in a project thread, not by the Runway loop (Joe, 2026-10-12: Runway doesn't fix Runway).

## What changes

The window's four tabs (Now, Queue, Decisions, Runs) become two: **Board** and **Runs**.

Board, top to bottom:

1. Banners: the project's error (detail, last log lines, Talk it through), a status fetch error, "All loops are paused".
2. A strip of four numbers: merged this round, spend today (with tokens), needs you, next tick.
3. Five columns, left to right. Each ticket sits in exactly one.
   - **Blocked**: status's `blocked` group, with "Waits on …".
   - **Needs you**: the `waiting` group (note: `reason`, else `waiting_on`), then errored tickets that aren't
     running or done (note: the error kind in words). Same rule as the side panel's Needs you section.
   - **Up next**: `ready_auto` then `ready_prep`, in queue order. The first is "Next in line"; prep tickets are tagged.
   - **Running**: the `running` group plus the heartbeat's live ticket. The first one is a large card: elapsed,
     attempt, harness, phase strip (sync, prep, agent, check, merge), last three log events. Loop off: "Loop is off",
     how many are ready, and Start. A dead run's stopped line shows in red above it.
   - **Done this round**: tickets with a `done` outcome in `_pm/runway-runs.jsonl` since the last `finish` row,
     newest first, with minutes and cost of their agent calls. A note under the column says what finish does.
4. The activity log as a drawer: closed it shows the latest event on one line; open, the full list. The open state
   is remembered.

Clicking a card opens a details pane on the right (a second click, or the close button, shuts it): title, the note,
the packet plus a note field and Go / No when it waits on Joe, Talk it through (waiting, errored, running, done), Resume
worker when status marks the ticket `resumable` (done tickets too: the worktree is recreated from the kept branch), the
tracker link (done tickets keep theirs, since status loads closed issues), and the ticket's prep / agent / check /
outcome rows from the runs log. A done ticket's session answers questions about what got done and posts nothing.

Under Done this round, **Open last review** shows when status says `review_resumable`: it runs `discuss --review`, the
last finish review's own claude session, to ask what the reviewer found. That review covered the previous round; the
cards above it get reviewed at the next finish. Which session to open: the worker's, per ticket, because the review
is one per round and covers every ticket in it.

Every way into the window (sidebar, side panel Details or red card, menu items, notifications) lands on the board,
with the named ticket's details open.

## Rules that don't change

- No drag and drop. Moving a card would be a tracker change, and a go only counts when Joe presses Go or types it.
- Go and No still run `runway go|no` through `DecisionsFeed`, once per ticket, only from those buttons.
- Status is fetched once a minute (it calls the tracker). The runs log is re-read every 10 seconds.
- The app still holds no logic of its own beyond laying out what the engine reports.

## Where it lives

- `factory/app/Sources/RunwayCore/Board.swift`: `Board.build`, `RoundLog` (this round's merged tickets, a
  ticket's history), `BoardStats`. Unit tested in `BoardTests.swift`.
- `factory/app/Sources/RunwayBar/BoardView.swift`: the board, cards, Running card, details pane, drawer.
- `QueueTabView.swift` and `DecisionsTabView.swift` are gone; their parts moved into the board.

## Acceptance

- [ ] `swift test` passes, including `BoardTests`.
- [ ] On Joe's Mac the window opens on the board for a loop with running, waiting, ready, blocked and done tickets.
- [ ] Clicking a waiting card shows its packet and Go / No; answering shows "Answered".
- [ ] A notification or the side panel's Details opens the board with that ticket's details open.
