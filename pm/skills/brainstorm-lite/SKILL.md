---
name: brainstorm-lite
description: One-session planning for small, low-fog work — a short interview, 2-3 approaches, an approved design saved to the project's _pm/ before any code. Use BEFORE building, adding, or changing anything when the work plausibly fits one session — "let's add X", "build a quick Y", "change how Z works", "design this feature" — even when the user doesn't say "plan" or "brainstorm". Do NOT use for foggy multi-session work (chart a wayfinder map instead) or for trivial one-step edits (just do those). This is the small-work planning primitive in a Matt-Pocock-primary stack; it replaces the superpowers brainstorming skill.
---

# Brainstorm Lite

Small work still deserves a design — unexamined assumptions waste the most time on "simple" tasks. But small work deserves a *small* design: a short interview, a real choice between approaches, a page or less of decisions, then build. The full ceremony belongs to bigger pipelines.

## The gate — check before anything else

Two questions decide whether this skill is even the right tool:

1. **Does the work plausibly fit one session?** Count the unknowns, not the files.
2. **Can you name the destination now?** One sentence, concrete enough to test against.

Both yes → proceed. Either no → **stop and say so**: this is fog-of-war work; recommend charting a wayfinder map (`/wayfinder`) instead. Matt's rule runs both directions — "if it fits one session, plan it in one session" — and stretching a lite brainstorm over a map-shaped problem produces a bad map and a worse brainstorm.

At the other extreme: a genuinely trivial change (rename, one-liner, config flip) needs no design at all. Don't ceremonialize it — do it, verify it, done.

## The process

**1. Read before asking.** If the project has `_pm/`, read `skeleton.md` (the why) and `TASKS.md` (the now) first. Check the code the change touches. Questions the context already answers are questions you don't ask.

**2. Interview — short.** Questions one at a time, five or fewer total, multiple-choice where possible. You're after purpose, constraints, and what done looks like — not exhaustiveness. If the design genuinely wants deeper questioning (real trade-offs, domain terms to pin), hand the questioning phase to `/grilling` — it's the stronger interview and this skill composes with it rather than competing.

**3. Approaches — two or three, with a recommendation.** Lead with the one you'd pick and why. Name the trade-off each carries. YAGNI ruthlessly: strike every feature the destination sentence doesn't require.

**4. Design — a page or less.** What's being built, its boundaries (what it deliberately does NOT do), the error cases that matter, and how it will be verified. Scale to the work: three sentences is a legitimate design for a small feature.

**5. The approval gate.** Present the design and get an explicit yes before writing any implementation code. No scaffolding, no "I'll just set up the files" — the gate exists because reversing unapproved work costs more than waiting. This gate is the whole reason the skill exists; everything else is negotiable, this isn't.

## The artifact — one home, always

The approved design gets written down where the project keeps its thinking:

- Project has `_pm/` → `_pm/decisions/YYYY-MM-DD-<slug>.md` (use the decisions template if present).
- No `_pm/` → `docs/plans/YYYY-MM-DD-<slug>.md`.
- **Once Switchyard is live** (Joe's tracker): attach the design as a document on the ticket instead — the ticket is the home, the file locations above are the interim.

Write it *at approval time*, before implementation starts — a design written after the build is a changelog wearing a costume.

## Terminal state

Hand off to implementation **in this same session** — directly, or through Matt's `/tdd` or `/implement` for disciplined execution. Do not invoke another planning pipeline (no writing-plans, no second interview); the design you just got approved IS the plan. When implementation completes, `verify-before-done` governs the claim.
