---
name: fast-grill
description: The pace rule for grilling. When /grilling, wayfinder charting, or the /to-tickets approval step is about to put a round of questions to the user, sort them - technical questions go with their recommended answer to a second-vendor seat (Astra via Ringer) and come back as rulings, and only taste, one-way-door, user-challenge, and seat-split questions reach the user. Use whenever a grilling round is about to be shown in a repo bound to pm's WORKFLOW.md or whose wayfinder map Notes say "fast grill", and whenever the user says "fast grill", "take the defaults", "just decide the technical stuff", "only ask me taste questions", "send the technical ones to Astra", "speed through this". Not for discovery (it riffs, it doesn't grill), not for prototype tickets (reacting to the prototype is the point), and never a reason to skip the fact-finding that /grilling already delegates to sub-agents.
---

# Fast grill

`/grilling` works a design tree in rounds: it computes the frontier, numbers each question, and prints a recommended answer under every one. On Joe's projects the recommendation gets a "yes" about nineteen times in twenty, and on technical questions he is deferring to the model anyway. Fast grill spends those nineteen for him, but not by self-approval: the technical questions and their recommendations go to a **second seat from another vendor** (Astra, through Ringer), and what comes back agreed becomes a ruling he can reverse. He sees only the questions where his answer changes the work, plus the ones the two models split on.

The grill still runs. Fast grill sits between the frontier `/grilling` computes and the round the user sees. Nothing about the tree, the rounds, or the fact-finding changes. This is the `cross-review-gate` consensus rule applied to rulings instead of findings: panel agreement applies under standing consent; a split stops for the human.

## The four buckets

Sort every frontier question before it is shown. When a question could sit in two buckets, the tie-break is below the table.

| Bucket | Action | Looks like |
|---|---|---|
| **Technical** | Send to the second seat with the recommendation. Agreed → ruling, not shown. Split → shown as a seat split. | Library or pattern choice inside the stack already chosen, file layout, naming, which table owns a field, error-handling and retry policy, test seam, cache strategy, endpoint shape, anything the codebase or the stack reference can settle. |
| **Taste** | Ask. | Anything a user sees or feels: flow order, wording, defaults a client will notice, what ships first, what "done enough" looks like. Anything the map's Notes list under *Taste for this effort*. |
| **One-way door** | Ask. Never auto-take, whatever the seat says. | Migrations or transforms on live data, deletes, anything public or production-facing, spend, credentials, anything touching client data or NDA material, an architecture choice that would take more than a session to unwind. |
| **User challenge** | Ask, with the disagreement spelled out. | The recommended answer contradicts something the user already said, in this session or on the map. Show what they said, what is recommended instead, why, and the cost of each being wrong. |

**Tie-break: technical wins.** Uncertain between technical and taste, send it to the seat; the seat can hand it back as taste (see below). The user said plainly he would rather reverse a ruling than answer a question, and the ledger makes reversal a one-line comment. The only bucket that never yields to that tie-break is the one-way door: uncertain whether something is reversible, ask.

## The second seat

The technical bucket for a round is **one Ringer task**, engine `codex`, model `gpt-6-astra` (the house cross-vendor seat; `gpt-5.6-sol` when Astra is quota-blocked). Kit: `Agent/Ringer/local/templates/grill-review/`. The spec inlines every technical question with its number, the options, Claude's recommendation and reason, and the read-only context the seat needs (repo path, the map's Decisions so far, the intent). The seat returns one verdict per question:

- **agree** — the recommendation stands. Becomes a ruling.
- **disagree** — with a reason and an alternative. Becomes a **seat split** question for the user: both positions, one line each, the cost of each being wrong.
- **taste** — the seat judges this is the user's call, not a technical one. Goes to the user as a taste question.

Rules that keep this honest:

- **It runs under Ringer, like every delegated call.** Never an inline "quick check" with Codex. Lint the manifest; the check verifies every question got a verdict with a reason, and a disagree got an alternative.
- **Do not block the round on it.** Dispatch the seat, then ask the taste, one-way-door, and user-challenge questions in the same turn. Fold the seat's verdicts into the next round: agreed items land in the ledger, splits and taste hand-backs join that round's questions. This is `/grilling`'s own rule for running explorations, applied to the seat.
- **One seat task per round, not per question.** A round's technical bucket is one packet. A round with an empty technical bucket dispatches nothing.
- **Degraded mode, stated out loud.** Codex unavailable, quota-blocked, or the user says "no seat this time" → take the recommendation directly and mark each ruling `(unseated)`. Say in the round that the seat was skipped. A ruling made without the seat is still reversible the same way.
- **The seat never sees a one-way door.** Those go to the user regardless.

## The round

Print the round in three parts: what the seat settled, what the seat sent back, then the user's questions in `/grilling`'s own format.

```
Round 3 · frontier: 7 questions

Rulings from round 2's seat (Astra agreed 3, split 1):
  Q3 retry policy → exponential, 3 attempts
  Q4 where the sync log lives → own table, not a field on Job
  Q7 naming → SyncRun / SyncRunLine, per the glossary

Sent to Astra this round (3): Q9, Q10, Q12 → back next round.

❓ Q6 - Seat split · test seam
   Claude: fake at the Data API client (fastest to fake; cost if wrong: rewrite ~4 tests)
   Astra:  fake at the layout boundary (the client is thin; cost if wrong: slower tests)
➡️ Claude's. The client is where the failures actually happen.

❓ Q5 - What the operator sees when a sync half-fails: …
➡️ b. Applied lines stay, failed lines listed for retry.

❓ Q8 - User challenge: you said "one screen for everything" …
➡️ Keep one screen; revisit after the prototype.
```

A settled question still reshapes the tree: the questions behind it join the next frontier. A round with nothing left to ask is still a round: print the rulings and the in-flight list, then move on. The user can pull any ruling back into play by replying with its number.

## The rulings ledger

Every settled technical question becomes one line. Four parts: what was decided, why, what it costs if wrong, who agreed.

```
## Rulings (fast grill)
- Retry policy: exponential, 3 attempts · standard for this stack · cost if wrong: a config change · Astra agreed
- Sync log: own table · keeps Job narrow · cost if wrong: one migration before go-live · Astra agreed
- Test seam: around the Data API client · where failures happen · cost if wrong: rewrite ~4 tests · seat split, Joe chose Claude's
- Naming: SyncRun / SyncRunLine · glossary match · cost if wrong: a rename · unseated (Codex quota)
```

Where it goes:

- **Inside a wayfinder ticket** → the ticket's resolution comment, under the answer. The map's *Decisions so far* line gists the answer only; the rulings live in the ticket, as every decision does.
- **Charting** (the two grills that name the destination and map the frontier) → the map body, a `## Rulings` section under *Notes*, so every later session inherits them.
- **`/to-tickets`** → the approval message, above the published list.
- **Plan mode, one-session work** → the plan itself, last section.

A reversal is a reply naming the ruling: "reverse the sync-log one, it's a field on Job." Re-open that branch of the tree, recompute the frontier, carry on. Do not re-grill the rest, and do not re-send a reversed ruling to the seat; the user's word ends it.

## Where it applies

- **Charting a map.** Wayfinder grills twice at the start: the destination, then the frontier breadth-first. Both run fast. The destination question itself is always taste.
- **Working a grilling ticket.** Every round.
- **`/to-tickets`, step 4.** Granularity and blocking edges are technical unless the user has marked a slice as theirs; the proposed breakdown goes to the seat as one packet. Print the breakdown with the rulings above it, publish, and tell the user to edit any ticket they disagree with.
- **Plan mode on one-session work**, when the plan is being grilled.
- **Not discovery.** Discovery riffs; it has no frontier and no recommendations to take.
- **Not prototype tickets.** The user's reaction to the artifact is the whole ticket.

## Ending a grill

`/grilling` ends when the frontier is empty and the user confirms a shared understanding. Fast grill keeps that confirmation, once, at the end: wait for the last seat packet, show the full rulings ledger and the taste answers together, and ask for the one nod. That is the shared understanding, and it is the last question of the session.

## The map Notes line

When a map is charted, put this under `## Notes` so every session that opens the map runs fast without being told:

```
Fast grill (pm `fast-grill`): every grilling round on this map sends technical
questions with their recommended answers to the Astra seat via Ringer and
ledgers the agreed ones as Rulings; only taste, one-way-door, user-challenge,
and seat-split questions are asked. Seat: on.
Taste for this effort: <the two or three things the user wants to decide personally>
```

Two dials. *Seat: on | off* turns the second seat off for a map where a Codex call per round isn't worth it (a docs effort, a throwaway). *Taste for this effort* is the list the user actually wants to decide; a client-facing screen might say "wording, flow order, anything the client demoed on," a data migration might say nothing and run almost silent.

## Where this sits

The schedule (which stages run under fast grill) belongs to pm's `WORKFLOW.md`; this file owns the buckets, the seat, the round, and the ledger. Seat craft (spec, check, engine, watch surface) is the `ringer` skill's; the seat's kit lives in Ringer's `local/templates/grill-review/`. `/grilling` and `/wayfinder` are Matt Pocock's and are not edited. The bucket split is adapted from gstack's `/autoplan` (Mechanical / Taste / User Challenge, 2026-09-06 source review); the ruling line is Superpowers' "rulings, not stalls" format; the second seat is Joe's addition the same day, so that a technical ruling is never the recommending model approving itself.
