# Spec: review gate after a Runway round (merge on pass, fix ticket on fail)

Tracker entry: #27 (tickets #28-#33). Moved here from the issue body on 2026-10-10.

## Problem

When Runway's queue empties, `finish()` reviews `runway/integration`, makes one fix pass, runs the check and opens a draft PR. It always ends at "Ready for review", findings or not, and Joe (or Marvin, his Codex assistant) reviews and merges by hand. Nothing turns a failed review into work: the hourly sweep routine files leftover findings an hour later. PR #20 was opened, and merged, with the check exiting 1.

## Goal

After a round: an adversarial review gives a verdict. **Pass** merges the reviewed commit into `main`. **Fail** files a ticket carrying the blocking findings, which goes back through the queue, and the next finish reviews again. This adopts the completion contract in `factory/scripts/OBSERVER.md` (PR #24).

## Rules

- A failing check (run after the last edit) always fails the round.
- Each done ticket's acceptance criteria are mapped to evidence; a criterion with none is a blocking finding.
- Only blocking findings fail the round (bugs, a ticket missing or half done, tickets that don't fit together). Non-blocking ones go in the PR body.
- A finding both seats raise is blocking unless the judge shows it's wrong; a one-seat finding is verified against the code first.
- Reviews must name the exact SHA they read; a stale report is discarded and that seat counts as missing. No valid seat means fail.
- One repair round per batch: review, one fix ticket, review again; a second fail parks the fix ticket `needs-human` with both reviews.
- Fix tickets dedupe by head, check and finding signature.
- One-way doors (migrations, removed APIs, plugin migrations, any `needs-human` ticket in the batch) never auto-merge.
- Merge only the reviewed SHA (`gh pr merge --match-head-commit`).

## Modes

`"merge"` in `runway.json`: `off` (today's behaviour, unchanged), `shadow` (verdict and fix tickets, no fix pass, no merge; the PR says what it would have done), `on_pass` (shadow plus the merge). This repo goes to `shadow` first; Joe watches a few rounds, then decides on `on_pass` (Joe, 2026-10-09).

## Tickets

Sub-issues of #27. All wait for #7 (engine moves into pm).
