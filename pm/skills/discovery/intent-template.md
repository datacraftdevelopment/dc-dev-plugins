# Intent: <short title>

Author: <name>. Status: draft | accepted | superseded. Date: YYYY-MM-DD.
Source: <what prompted this — conversation, article, incident, client request>

## Problem

What's wrong or missing, in the originator's own terms. Who feels it, how often, what it costs.

## Proposed outcome

What "reached" looks like — the destination, concrete enough to measure against. Not a design.

## Acceptance

How we'd know this worked — in observable terms, written **now**, before anything is built.

Each line is a check a person can actually perform: what you do, and what should happen. Not tests, not a QA plan — the outcome restated so it can be *checked*, and checked **more than once**: against the local article before shipping, and against production after. The same lines both times.

**Write them for a stranger.** Whoever adjudicates this will not have been in the room — that is the entire point of adjudication, and it is why these are written now rather than at the end. A check that needs you to explain it can only be executed by the one party disqualified from executing it: the person who did the work.

- [ ] <do this> → <this happens>
- [ ] <do this> → <this happens>

Three or four is usually right; a long list means this is really several intents. Where a check can't be automated, say how it's done by hand — a named manual check beats a missing one. Where a check can't be performed at all, say that too; an honest gap here is a decision to make now rather than a surprise at Ship.

**If you can't write a single line here, the Proposed outcome isn't concrete yet.** Go back up and sharpen it — that's the signal this section exists to give.

## Affected users and systems

People, repos, services, files, external systems. Anything that changes or must be consulted.

## Constraints

What's fixed: technology, policy, budget, timeline, things that must not change.

## Open questions

The fog — decisions you can see coming but can't phrase sharply yet. Leave them open; the next stage resolves them.

## Size call

One session → build it (plan mode / `/implement`). Multi-session → `/wayfinder`, destination: "<one sentence from Proposed outcome>".

Map Notes for charting (fast grill, seat on): Taste for this effort: <the two or three things the originator wants to decide personally; blank means almost everything technical runs silent>.
