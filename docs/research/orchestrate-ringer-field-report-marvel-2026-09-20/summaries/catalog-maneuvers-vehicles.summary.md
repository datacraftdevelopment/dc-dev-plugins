# Fix Summary

## Summary

`generate-reference-catalog.js` now also writes `context/catalog/maneuvers.md` (59 team
maneuvers) and `context/catalog/vehicles.md` (46 vehicles), and lists both in
`00_INDEX.md` with their counts. Both follow the existing conventions: generated-from-the-DB
header block, a quick-list table, one `### Name` per entry, a `*Source: <book>*` line, and all
text run through the script's `stripHtml` helper.

Maneuvers get the full rules text from `element_display` (falling back to `short_description`),
A-Z, source noted per entry.

Vehicles are the harder table: `element_display` comes in two shapes — a flat run of
`<p><strong>Label</strong></p><p>value</p>` pairs, and a pre-gen block using `<h5>` stat
headings, `<strong>Flight Speed: </strong>12` paragraphs and `<ul>` power/note lists. One
block walk handles both: a bold-only paragraph or a stat heading opens a field, list items and
following paragraphs fill it, anything past the last field (or after a `Profile` heading) is
prose. Each entry renders as a compact `- **Label:** value` list (bullets when a field holds
several sentences), then its prose. The shared "Vehicles and Military Equipment" damage
boilerplate, repeated verbatim on 9 rows, is printed once at the top instead. Entries are
grouped under `## <source book>` headings. A leading `Vehicle:` field that just restates the
vehicle's name is dropped as an echo.

Output is deterministic and no other catalog file changed.

## Files Changed

- `scraper/scripts/generate-reference-catalog.js` — new maneuvers & vehicles section
  (`splitVehicleBoilerplate`, `htmlBlocks`, `isFieldLabel`, `parseVehicle`, `vehicleBlock`),
  plus two new `indexRows` entries and an index note.
- `context/catalog/maneuvers.md` — new, generated, 59 entries.
- `context/catalog/vehicles.md` — new, generated, 46 entries.
- `context/catalog/00_INDEX.md` — the two new rows plus a one-line note that these are play
  references, not character-creation picks.
- `fix-summary.md` — this file.

## Verification

    python3 .../marvel-tickets/verify_scraper.py catalog
    verify_scraper: passed

Also checked by hand against a read-only copy of the real DB: every word of text in every
`element_display` (minus the shared boilerplate and the dropped name echo) survives into its
entry, for all 59 maneuvers and all 46 vehicles. No new integrity warnings. The throwaway
`scraper/data/` copy and `scraper/node_modules` symlink used while iterating are gone;
`git status` shows only the five files above.

## Assumptions

- Maneuvers carry no level or team-requirement column in the DB (a level appears only inside
  some names, e.g. "Basic Offensive (Level 1)"), so the file's header points at the source
  books for eligibility rather than inventing the data.
- Vehicles are grouped by source book (their stat-block format differs per book); maneuvers
  stay one A-Z list with a per-entry source, matching `traits.md`/`occupations.md`.
- `short_description` is only printed when no profile prose was parsed and no field already
  says the same thing, to avoid repeating the text twice in one entry.
- The index's "last modified" footer reads the DB's mtime. The verify script's DB copy does not
  preserve mtime, so the committed line was set back to the real DB's date (2026-08-19); a
  normal run against the real database produces that value.
