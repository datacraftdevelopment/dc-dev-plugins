# Fix Summary

## Summary

Replaced `apps/marvel/README.md`'s create-next-app boilerplate with a real orientation doc: what the app is (Build Ledger explains every total), the seven routes, the five-part layout (`src/domain`, `src/persistence`, `src/features`, `src/catalog`, `convex/`), how to run it (the two launch configs plus the one-time `CONVEX_AGENT_MODE=anonymous npx convex dev --once` setup, and the note that `.convex/` data is per-checkout), how to test, how to regenerate the catalog snapshot, and the no-login/localhost-only warning.

Rewrote the stale `> **DB caveat:**` paragraph in `context/power-sets-rules.md` (the "always resolve to a subtype" section). Verified against the live DB that the fix landed on 2026-07-10: `power_sets.player_selectable` now correctly flags the four parent sets (Elemental Control, Magic, Melee Weapons, Omniversal Travel) as 0, alongside four special sets (Iconic Item Powers, Stunts, Narrative, Narrative Limitations). 8 rows flagged 0, 44 flagged 1. The paragraph now says the flag can be trusted for "is this set pickable," while keeping the surrounding rule that a picked parent still needs to resolve to a named subtype on the sheet.

## Files Changed

- `apps/marvel/README.md` — full rewrite, boilerplate replaced.
- `context/power-sets-rules.md` — one paragraph rewritten (the DB caveat under "Always Pick Subtypes, Not Parents"). Nothing else in the file touched.

## Verification

Query run read-only against `/Users/joe/Agentic-Mini/RPG/Marvel/scraper/data/marvel-rpg.db`:

```sql
SELECT name, category, player_selectable FROM power_sets WHERE player_selectable = 0 ORDER BY category, name;
-- Iconic Item Powers | iconic_items_only | 0
-- Stunts              | learned_in_play   | 0
-- Narrative           | narrator_only     | 0
-- Narrative Limitations | narrator_only   | 0
-- Elemental Control   | parent            | 0
-- Magic               | parent            | 0
-- Melee Weapons       | parent            | 0
-- Omniversal Travel   | parent            | 0

SELECT player_selectable, COUNT(*) FROM power_sets GROUP BY player_selectable;
-- 0 -> 8
-- 1 -> 44
```

Then ran the required check from the worktree root:

```
python3 /private/tmp/claude-501/-Users-joe-Agentic-Mini-RPG-Marvel/4ecb59dc-1562-45bb-a475-e78c6af427d7/scratchpad/marvel-tickets/verify_docs.py
```

Last line: `verify_docs: passed` (first run failed with "README uses an em dash"; rewrote the README and the new DB-note paragraph without em dashes, then it passed).

README word count: 577 (within the 300-700 range). Every `src/...` and `convex/...` path in backticks was checked against the actual tree (`find`/`ls`) before writing.

## Assumptions

- The task said "line ~30" for the caveat; it was at line 30 in the file as found, matching exactly.
- Kept the existing pre-2026-07-10 em dashes elsewhere in `context/power-sets-rules.md` untouched, since the task scoped the edit to only that one paragraph and the verify script only flagged the README.
- README covers `src/domain/play` and `src/persistence` at the directory level rather than enumerating every file, since the task's brief only named `evaluateCharacter`, `browser-storage`/Convex adapters, and the four top-level dirs plus `convex/`.
