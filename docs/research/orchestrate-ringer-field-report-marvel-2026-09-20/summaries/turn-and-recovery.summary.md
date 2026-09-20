# Fix Summary

## Summary

Two play-sheet gaps closed, both in the rules the sheet already quotes.

**Start of turn.** New pure module `src/domain/play/turn.ts` with `startOfTurn(state, sheet)`. It takes 5 Health for each of Ablaze, Bleeding and Corroding through `adjustResource`, so the track's floor of −maximum holds, and returns `{ slug, name, amount }` per condition. With none of the three active it returns the same state object and an empty list. Poisoned is left out with a comment saying why: it needs a Resilience check against TN 18 first, which is the table's call.

**Karma recovery.** Same module: `RECOVERY_TARGET_NUMBER = 10`, `recoveryRoll(sheet, track)` (Resilience for Health, Vigilance for Focus, built from `abilityCheck` and relabelled), and `recover(state, sheet, track, roll)`. No Karma returns the same state and `'no-karma'`. Otherwise the Karma goes either way; a success recovers `damageFor(roll, sheet.identity.rank, sheet.abilities[ability]).total`, which doubles on a Fantastic roll and counts the M as 6. The gain is clamped by `adjustResource`, while the reported `amount` is what the dice actually gave. A Health recovery clears Bleeding.

**Sheet.** `Start my turn` sits under the condition chips with a `role="status"` line naming each loss ("Bleeding: lost 5 Health.") or saying nothing happened. Each of the Health and Focus tracks gained a `Spend 1 Karma to recover …` button, disabled at 0 Karma or a full track, that rolls `rollD616(rollDie)`, applies `recover()`, and reports the result with the faces. Every state change goes through the existing `change()` helper, so saving and the concentration rules are untouched. No new CSS: the button reuses `.track-controls` / `.button`, the status lines reuse `.track-note muted` and `.muted`.

## Files Changed

- `apps/marvel/src/domain/play/turn.ts` (new)
- `apps/marvel/src/domain/play/turn.test.ts` (new, 7 tests)
- `apps/marvel/src/domain/play/index.ts` (two export lines)
- `apps/marvel/src/features/sheet/SheetView.tsx` (imports, two `ResourceTrack` props, two handlers, the turn button)

## Verification

```
python3 .../marvel-tickets/verify.py turn-and-recovery.acceptance.test.ts turn-and-recovery-sheet.acceptance.test.tsx
```

```
verify: $ npx next typegen
verify: $ npx vitest run
verify: $ npx tsc --noEmit
verify: $ npx eslint src
verify: all steps passed
```

Whole suite, tsc and eslint passed on the first run, both acceptance files included.

## Assumptions

- The recovery check resolves against `recoveryRoll(sheet, track).modifier`, not the bare ability score, so the check the sheet offers and the check it resolves are the same number. That modifier is the ability score plus any Mighty/Discipline-style non-attack bonus. The amount recovered still uses the plain `sheet.abilities` score, as the ticket says. Failsafe has no such bonus on Resilience or Vigilance, so neither acceptance test distinguishes the two readings.
- `recoveryRoll` returns `Omit<RollRequest, "modifiers">`, matching `abilityCheck`, `attackRoll` and `initiativeRoll` in `roll-request.ts`; `prepareRoll` is what attaches modifiers everywhere else in this module.
- The recovery roll is thrown plainly rather than through `rollFrom`, so it does not open the Roller tray or pick up automatic edges and troubles. No Karma may be spent on it, so there is no reroll to offer.
- No new CSS rules needed.
