# Fix Summary

## Summary

Read-only rules audit of `docs/PbP_Combat_Rules.md` and `docs/Marvel_System_Analysis.md` against `context/catalog/`, `context/*.md`, and `rules/demiplane/` chapter text, in that order of authority. Neither doc was edited. The report lists 12 findings (6 wrong, 5 misleading, 1 outdated wording) and 18 verified-correct rules statements.

The errors cluster in three areas. Karma: both docs give the recovery formula as Marvel die times rank and drop the ability score the rulebook adds, and the System Analysis states Karma equals rank without the Heroic tag requirement. Damage reduction: the PbP doc subtracts DR from the damage total, but DR reduces the damage multiplier and zeroes the attack out entirely below 1. Arithmetic: the Marvel die averages 4.33, not 3.5, because a 1 counts as 6, so every average-damage figure built on 3.5 is low. One System Analysis passage also prices power picks at a flat 16 for Rank 4, ignoring the thematic bonus in exactly the single-power-set case that earns it.

The big structural analyses hold up. The iconic-item and Power Cosmic sections verify claim by claim, including Mjolnir at Power Value 22 with ten of its sixteen powers already on Thor's sheet, and Reverbium as the one damage-multiplier bonus that stacks.

## Files Changed

- `docs/reviews/2026-09-20-rules-docs-crosscheck.md` — new, uncommitted. The audit report.
- `fix-summary.md` — new, this file.

No other file touched. Nothing staged, nothing committed.

## Verification

```
python3 /private/tmp/claude-501/-Users-joe-Agentic-Mini-RPG-Marvel/4ecb59dc-1562-45bb-a475-e78c6af427d7/scratchpad/marvel-tickets/verify_crosscheck.py
```

Last line:

```
verify_crosscheck: 12 finding(s); passed
```

The script confirms every finding quotes text that really sits at the cited line, and that each cited rule source exists.

## Assumptions

- The scraped database is not in this worktree and `better-sqlite3` is not installed, so `query-db.js` and `check-integrity.js` could not run. Catalog-tier claims were checked against the generated files in `context/catalog/` instead.
- House rules the PbP doc deliberately introduces were excluded: popcorn initiative, post format, resolving incoming damage in your own post, the team-tactics options. The Combat Reflexes pre-empt at `docs/PbP_Combat_Rules.md:17` was read as one of those and is noted in the Summary rather than listed as a finding.
- Design opinions and probability judgments (the Well-Built Character Test, the AI enforcement tiers) were treated as not-rules-statements and left alone.
- `context/catalog/powers/basic-powers.md` lists Power Cosmic with no prerequisites while the Secret Wars text lists Rank 5 plus the origin. The catalog row looked lossy rather than errata-current, so the System Analysis was judged against the rulebook there. Recorded under Not checked.
