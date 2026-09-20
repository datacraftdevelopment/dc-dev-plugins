# Fix Summary

## Summary

The read-only Profile now shows what a build owes to trades and Narrator overrides.
`ProfileView` reads `evaluation.record` (the record as played) and builds a list of
plain-words lines: power picks traded for ability points or traits, extra power picks
granted by override, ignored prerequisites, and marked Getting Schooled boxes with the
rank being climbed to. Singular and plural are handled on both sides of a trade
("1 power pick traded for a trait", "2 power picks traded for 2 traits") and on the box
count ("1 trait box", "3 ability, 1 power boxes").

The section renders only when at least one line exists, sits in the main column after
Powers and items and before Alternate forms, and is a `<section aria-labelledby>` with an
`<h2>` reading exactly "Build adjustments" wrapping a single `<ul>`. The two override
lines carry `data-override="true"` on the `<li>`; trade and Getting Schooled lines do not.
Override lines also colour the phrase "by Narrator override" with the existing
`.override-word` class, the same word the Builder's ledger uses. The `<ul>` reuses
`.plain-list`, already used by the Alternate forms list. No CSS changes.

## Files Changed

- `apps/marvel/src/features/profile/ProfileView.tsx` — added the `adjustmentLines` helper
  (a local `count` pluralizer and a `NarratorOverride` span) and the "Build adjustments"
  section; imported `markedBoxes` and the `CharacterRecord` type.
- `apps/marvel/src/features/profile/profile-adjustments.test.tsx` — new: singular trade
  wording, multi-kind box wording with the target rank, singular "box", and absence of the
  section when nothing is adjusted.

## Verification

```
python3 /private/tmp/claude-501/-Users-joe-Agentic-Mini-RPG-Marvel/4ecb59dc-1562-45bb-a475-e78c6af427d7/scratchpad/marvel-tickets/verify.py profile-adjustments.acceptance.test.tsx
```

Last lines:

```
verify: $ npx next typegen
verify: $ npx vitest run
verify: $ npx tsc --noEmit
verify: $ npx eslint src
verify: all steps passed
```

The full vitest suite, tsc and eslint all passed with the acceptance tests copied in.

## Assumptions

- The trade rate is 1:1, as the ledger and `evaluate-character` treat it, so one traded
  pick reads as one ability point or one trait.
- The Getting Schooled line is gated on boxes actually being marked, not on
  `rules.gettingSchooled`. A record with marked boxes and the switch since turned off
  still shows what was marked; nothing can be marked while it is off.
- The rank in the Getting Schooled line is `advancement.completedRank + 1`, the rank the
  marked boxes climb toward.
- `trades.itemPowerPicks` and `trades.advancementPurchases` are bookkeeping the ledger
  derives from items and boxes, not adjustments a reader chose, so they get no line.
- No new CSS rules needed.
