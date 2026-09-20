# Fix Summary

## Summary

Two gaps in the build ledger closed.

**Stat grid.** The ledger's `Derived statistics` grid now carries `Flight`, `Health DR` and `Focus DR`, in the same `<div><dt/><dd/></div>` shape as the rest. Flight renders only when `derived.speeds.flight` is defined; each DR cell only when `derived.damageReduction.<track>` is above 0. Order and conditions match what `SheetView.tsx` already does (Flight after Swim, then the two DR cells), so the ledger and the Play sheet read the same.

**Power picks sum.** The evaluator adds `advancement.powerBoxes` to `budget.power.available`, but neither the panel note nor the Markdown export mentioned them, so the arithmetic in the note did not reach the stated total for a character with a Getting Schooled power box marked. Both now say `+ N from Getting Schooled`, after the thematic bonus and before any override, and only when N is above 0.

- Panel: reads `evaluation.record` (the record as played) for both `trades` and `advancement`, so a PC whose party advanced past the chart does not get credit for boxes the evaluator already dropped. The phrase sits in its own `<span className="bonus-word">`, the class the thematic bonus already uses — no new CSS.
- Export: `powerAdjustments` now destructures `advancement` as well, and the `Power picks:` line passes `ev.record` instead of the raw `record`, for the same as-played reason. That line's totals come from `ev.budget`, so the two now come from one record.

## Files Changed

- `apps/marvel/src/features/builder/LedgerPanel.tsx` — three conditional stat cells; Getting Schooled span in the power picks note.
- `apps/marvel/src/exports/character-exporter.ts` — `powerAdjustments` carries power boxes; call site reads the played record.
- `apps/marvel/src/features/builder/ledger-panel.test.tsx` — new. Four tests: the grid with Failsafe (flight 15, Health DR 3, no Focus DR) and with Parallax (none of the three, speeds intact); the note naming 3 boxes and matching the budget, and staying quiet at zero.

## Verification

```
python3 /private/tmp/claude-501/-Users-joe-Agentic-Mini-RPG-Marvel/4ecb59dc-1562-45bb-a475-e78c6af427d7/scratchpad/marvel-tickets/verify.py ledger-grid.acceptance.test.tsx
```

Last lines:

```
verify: $ npx next typegen
verify: $ npx vitest run
verify: $ npx tsc --noEmit
verify: $ npx eslint src
verify: all steps passed
```

Whole vitest suite (existing tests plus the four acceptance tests copied in), tsc and eslint all clean.

## Assumptions

- Reused `bonus-word` for the Getting Schooled phrase rather than asking for a new class. Boxes are earned budget, same as the thematic bonus, so the shared colour is honest; if you want them visually distinct from the thematic bonus, that needs a new rule in `globals.css`.
- Placed Flight and the DR cells at the end of the grid, following `SheetView.tsx` rather than pairing Health DR next to Health.
- Changed the export's call site to `ev.record`. Line 82's `record.advancement.remainingBoxes` still reads the raw record; left alone, it is outside this ticket.
