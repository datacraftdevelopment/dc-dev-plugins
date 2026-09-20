# Fix Summary

## Summary

Two safety nets for the scraper pipeline, both from real incidents.

**Node drift.** `scraper/.nvmrc` pins Node major `26` (the `node -v` on this machine today: v26.8.2). `scraper/scripts/preflight.js` warns when the running major differs from `.nvmrc`, then loads better-sqlite3 and opens an in-memory DB to exercise the native binding. On failure it prints the exact fix (`cd scraper && npm rebuild better-sqlite3`) and exits non-zero; on success it prints one line naming the Node version and that better-sqlite3 loaded. It works as a script, as `npm run preflight`, and as `require('./preflight').preflight()`. The require of better-sqlite3 is inside the function, so importing a script that requires preflight does not load the binding — `test-scrape-all-pipeline.js` asserts exactly that.

**Backups.** `scraper/scripts/lib/backup-db.js` exports `backupDb(dbPath, { now = new Date(), keep = 10 })`: copies the DB to `<dir>/backups/<basename>.<YYYY-MM-DD>-<HHMM>` in UTC, creating `backups/` as needed, adding a numeric suffix rather than overwriting, pruning to the newest `keep`, and returning the absolute path. It also copies a `-wal` sidecar when one exists — the DB runs in WAL mode, so a bare file copy can be missing the last committed writes. `scrape-all.js` (in `main()`, before the init-db stage) and `reparse-characters.js` (before `new Database(...)`) now call `preflight()` then `backupDb()` and print the path; `--no-backup` skips the copy.

## Files Changed

- `scraper/.nvmrc` — new; `26`
- `scraper/scripts/preflight.js` — new
- `scraper/scripts/lib/backup-db.js` — new
- `scraper/scripts/scrape-all.js` — requires added, `--no-backup` in `parseArgs`, preflight + backup at the top of `main()`, usage comment line
- `scraper/scripts/reparse-characters.js` — requires added, preflight + backup before the DB opens, usage comment line
- `scraper/package.json` — `"preflight": "node scripts/preflight.js"`
- `scraper/CLAUDE.md` — Node pin note in Setup, a "Safety nets" entry pair in Scripts Reference, and the two script entries updated
- `fix-summary.md` — this file

## Verification

```
python3 .../marvel-tickets/verify_scraper.py preflight
verify_scraper: passed
exit=0
```

Also run: `node --check` on both edited scripts and both new files (clean — neither script was executed); `node scraper/scripts/test-scrape-all-pipeline.js` → `PASS: scrape-all mandatory post-processing pipeline contract`; and a throwaway-tempdir exercise of `backupDb` confirming same-minute collisions get a `.2` suffix, the `-wal` sidecar is copied, `keep: 3` prunes to the newest three, and a missing DB returns `null`.

## Assumptions

- `.nvmrc` holds the major only (`26`), so patch upgrades don't produce noise; the verifier compares majors too.
- A Node/`.nvmrc` mismatch warns but does not fail — it's only a problem once the binding actually breaks, which check (b) catches.
- `preflight()` exits the process on failure by default; `preflight({ exitOnFailure: false })` returns `false` instead for a caller that wants to handle it.
- `backupDb` returns `null` when the DB file doesn't exist yet (fresh checkout before `init-db.js`), which keeps the two call sites to a few lines.
- Prune sorts by filename; the UTC stamp makes that chronological. The copy just taken is never pruned, even if `now` is backdated.
