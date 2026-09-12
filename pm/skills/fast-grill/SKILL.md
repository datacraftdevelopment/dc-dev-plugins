---
name: fast-grill
description: The pace rule for grilling. When /grilling, wayfinder charting, or the /to-tickets approval step is about to put a round of questions to the user, sort them - technical questions go with their recommended answer to a second-vendor seat (Astra via Ringer) and come back as rulings, and only taste, one-way-door, user-challenge, and seat-split questions reach the user. Use whenever a grilling round is about to be shown in a repo bound to pm's WORKFLOW.md or whose wayfinder map Notes say "fast grill", and whenever the user says "fast grill", "take the defaults", "just decide the technical stuff", "only ask me taste questions", "send the technical ones to Astra", "speed through this". Not for discovery (it riffs, it doesn't grill), not for prototype tickets (reacting to the prototype is the point), and never a reason to skip the fact-finding that /grilling already delegates to sub-agents.
---

# Fast grill

`/grilling` works a design tree in rounds: it computes the frontier, numbers each question, and prints a recommended answer under every one. On Joe's projects the recommendation gets a "yes" about nineteen times in twenty, and on technical questions he is deferring to the model anyway. Fast grill spends those nineteen for him, but not by self-approval: the technical questions and their recommendations go to a **second seat from another vendor** (Astra, through Ringer), and what comes back agreed becomes a ruling he can reverse. He sees only the questions where his answer changes the work, plus the ones the two models split on.

The grill still runs. Fast grill sits between the frontier `/grilling` computes and the round the user sees. Nothing about the tree, the rounds, or the fact-finding changes. This is the `cross-review-gate` consensus rule applied to rulings instead of findings: panel agreement applies under standing consent; a split stops for the human.

## The four buckets

Sort every frontier question before it is shown.

| Bucket | Action | Looks like |
|---|---|---|
| **One-way door** | Ask. Never auto-take, whatever the seat says. Never sent to the seat. | Migrations or transforms on live data, deletes, anything public or production-facing, spend, credentials, anything touching client data or NDA material, an architecture choice that would take more than a session to unwind. |
| **User challenge** | Ask, with the disagreement spelled out. Never auto-take. | The recommended answer contradicts something the user already said, in this session, on the map, or in the intent. Show what they said, what is recommended instead, why, and the cost of each being wrong. |
| **Taste** | Ask. | Anything a user sees or feels: flow order, wording, defaults a client will notice, what ships first, what "done enough" looks like. Anything the map's Notes list under *Taste for this effort*. |
| **Technical** | Send to the second seat with the recommendation. Agreed → ruling, not shown. Split → shown as a seat split. | Library or pattern choice inside the stack already chosen, file layout, naming, which table owns a field, error-handling and retry policy, test seam, cache strategy, endpoint shape, anything the codebase or the stack reference can settle. |

**Precedence, in that order.** A question that is a one-way door or a user challenge is asked, full stop, even when it is also technical and even when it is cheap to reverse; two models agreeing about a rename does not overrule the user's stated wish to keep the name. Anything the map's Notes reserve under *Taste for this effort* is asked. **Only then** does the tie-break apply: uncertain between technical and taste, send it to the seat, which can hand it back as taste. The user said plainly he would rather reverse a ruling than answer a question, and the ledger makes reversal a one-line comment. Uncertain whether something is reversible: it is a door, ask.

## The second seat

The technical bucket for a round is **one Ringer task**, engine `codex`, model `gpt-6-astra` at medium reasoning effort (the house cross-vendor seat; `gpt-5.6-sol` when Astra is quota-blocked). Kit: `_Core/Ringer/local/templates/grill-review/`. The spec inlines every technical question with its number, the options, Claude's recommendation and reason, and the read-only context the seat needs (repo path, the map's Decisions so far, the intent). The seat returns one verdict per question:

- **agree** — the recommendation stands, with a concrete reference the seat checked (the check refuses a bare "sounds right"). Becomes a ruling.
- **disagree** — with a reason and an alternative. Becomes a **seat split** question for the user: both positions, one line each, the cost of each being wrong.
- **taste** — the seat judges this is the user's call, not a technical one. Goes to the user as a taste question.
- **door** — the seat judges that acting on the answer would be hard to reverse, whatever its merit. Goes to the user as a one-way-door question. This is the second vendor's check on the bucket the recommending model must never be the sole judge of.

Rules that keep this honest:

- **It runs under Ringer, like every delegated call.** Never an inline "quick check" with Codex. Lint the manifest; the check verifies every question got exactly one verdict with a same-line reason, a reference on every agree, and an alternative on every disagree. An ambiguous packet fails and stays unsettled.
- **Do not block the round on it.** Dispatch the seat, then ask the door, user-challenge, and taste questions in the same turn. Fold the seat's verdicts into the next round: agreed items land in the ledger, splits, doors, and taste hand-backs join that round's questions. This is `/grilling`'s own rule for running explorations, applied to the seat.
- **One seat task per round, not per question.** A round's technical bucket is one packet. A round with an empty technical bucket dispatches nothing.
- **Degraded mode, detected and stated out loud.** The seat task's timeout is ten minutes and Ringer retries once. If the task fails and its worker log shows a quota, auth, or model-availability error, do not wait for the retry to burn: switch this map's seat to `gpt-5.6-sol` for the next round and say so. If Sol fails the same way, or the user says "no seat this time", take the recommendation directly and mark each ruling `(unseated)`, said in the round. A ruling made without the seat is still reversible the same way. A packet that fails on format (not on availability) is retried once by Ringer; if it fails again, its questions carry to the next round unsettled rather than being taken.
- **The seat never sees a one-way door or a user challenge.** Those go to the user regardless.

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
- **`/to-tickets`, step 4.** Granularity is technical unless the user has marked a slice as theirs; the proposed breakdown goes to the seat as one packet. **The blocking edges are not auto-taken.** They are executable input to `build-swarm`, not a reversible ruling: a missed edge becomes two dependent tickets dispatched in one wave. Print the breakdown with the rulings above it and the edges called out, and **publish on the user's nod**, the same single confirmation `/to-tickets` itself requires. Tell the user to edit any ticket they disagree with after.
- **Plan mode on one-session work**, when the plan is being grilled. Plan mode does not permit the Bash a Ringer dispatch needs, so a plan-mode grill runs `(unseated)` by construction; say so in the plan's Rulings section, or run one seat pass on the plan's technical rulings as the first act after the plan is approved and before any code, folding splits and doors back to the user.
- **Not discovery.** Discovery riffs; it has no frontier and no recommendations to take.
- **Not prototype tickets.** The user's reaction to the artifact is the whole ticket.

## Ending a grill

`/grilling` ends when the frontier is empty and the user confirms a shared understanding. Fast grill keeps that confirmation, once, at the end: wait for the last seat packet, show the full rulings ledger and the taste answers together, and ask for the one nod. That is the shared understanding, and it is the last question of the session. If the last packet is still out and the user wants to close, close provisionally: list the in-flight questions as *pending rulings*, land them in the ledger when the packet returns, and route any split or door to the user then.

## The map Notes line

When a map is charted, put this under `## Notes` so every session that opens the map runs fast without being told:

```
Fast grill (pm `fast-grill`): every grilling round on this map sends technical
questions with their recommended answers to the Astra seat via Ringer and
ledgers the agreed ones as Rulings; only taste, one-way-door, user-challenge,
seat-split, and seat-flagged door questions are asked. Seat: on.
Taste for this effort: <the two or three things the user wants to decide personally>
```

Two dials. *Seat: on | off* turns the second seat off for a map where a Codex call per round isn't worth it (a docs effort, a throwaway). *Taste for this effort* is the list the user actually wants to decide; a client-facing screen might say "wording, flow order, anything the client demoed on," a data migration might say nothing and run almost silent.

## Where this sits

The schedule (which stages run under fast grill) belongs to pm's `WORKFLOW.md`; this file owns the buckets, the seat, the round, and the ledger. Seat craft (spec, check, engine, watch surface) is the `ringer` skill's; the seat's kit lives in Ringer's `local/templates/grill-review/`. `/grilling` and `/wayfinder` are Matt Pocock's and are not edited. The bucket split is adapted from gstack's `/autoplan` (Mechanical / Taste / User Challenge, 2026-09-06 source review); the ruling line is Superpowers' "rulings, not stalls" format; the second seat is Joe's addition the same day, so that a technical ruling is never the recommending model approving itself. Revised the same day after a two-seat Ringer gate (record in dc-dev-plugins `.review-gate/2026-09-06-pm-014-fast-grill-build-swarm/`): doors and user challenges take precedence over the tie-break, the seat gained a `door` verdict, to-tickets publishes on the nod, degraded mode is detected rather than discovered, and the checker parses fields strictly.
