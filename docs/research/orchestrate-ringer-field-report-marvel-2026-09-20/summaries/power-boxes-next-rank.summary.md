# Fix Summary

## Summary

Getting Schooled power boxes now reach one rank up, end to end.

- `build-options.ts`: `PowerOption` gains `viaAdvancement`. `powerOptions()` counts spare power boxes as `advancement.powerBoxes` minus the advancement picks the character hasn't grown into yet (reason `advancement` and a minimum rank above the character's). With a spare box, an unselected power whose only unmet requirement is a rank exactly one above the character's becomes `available` with `viaAdvancement: true`. A shared `minimumRankOf` helper replaces the inline rank math so both the spare-box count and the option use the same number.
- `edit-character.ts`: `togglePower(record, slug, reason = "purchased")` stores the reason on the new selection. Removal is untouched.
- `evaluate-character.ts`: new error `advancement-powers-over-boxes` on path `advancement` when the picks that still need a box outnumber `advancement.powerBoxes`. The same `minimumRankOf` helper (now a context method, reused by `accountPowers`) means a pick stops needing a box once the character's rank reaches its minimum, so a party rank-up that zeroes the chart raises nothing.
- `sections.tsx` (PowerTree only): a `viaAdvancement` option toggles with reason `advancement`, and both it and an already-advancement pick show the meta label "Uses a Getting Schooled power box". No new CSS; the label is a plain `<span>` inside the existing `power-meta`.
- `advancement-powers.test.ts`: covers the two-rank reach staying locked, a missing prerequisite power keeping a next-rank power locked, per-pick box spending, the over-boxes message text, and a purchased (not advancement) next-rank pick still failing the plain rank check.

## Files Changed

- `apps/marvel/src/domain/character/build-options.ts`
- `apps/marvel/src/domain/character/edit-character.ts`
- `apps/marvel/src/domain/character/evaluate-character.ts`
- `apps/marvel/src/features/builder/sections.tsx`
- `apps/marvel/src/domain/character/advancement-powers.test.ts` (new)

## Verification

```
python3 /private/tmp/claude-501/-Users-joe-Agentic-Mini-RPG-Marvel/4ecb59dc-1562-45bb-a475-e78c6af427d7/scratchpad/marvel-tickets/verify.py advancement-powers.acceptance.test.ts advancement-powers-builder.acceptance.test.tsx
```

```
verify: $ npx next typegen
verify: $ npx vitest run
verify: $ npx tsc --noEmit
verify: $ npx eslint src
verify: all steps passed
```

Full suite: 24 files, 273 tests passing (count read from a deliberately-failed run used to confirm the new test file is picked up; the sentinel was reverted and the suite re-run clean).

## Assumptions

- Spare boxes gate availability but are not reserved per option: with one box, every eligible next-rank power reads as available, and picking one locks the rest. That is what the acceptance test asks for.
- `viaAdvancement` stays false for an already-selected power; the Builder reads the stored reason to decide whether to show the label on a selected row.
- The over-boxes check runs before the party early return in `checkAdvancement`, so a campaign PC is checked too.
- No new CSS rules needed.
