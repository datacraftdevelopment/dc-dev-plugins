---
name: adt-capabilities
description: >
  What the ADT `fm` CLI can and cannot actually do on the installed build, measured
  by running it rather than read from docs. Use BEFORE authoring fm layout or schema
  ops -- "add a button bar", "put a field in a portal", "set a tooltip", "can the CLI
  do X", "why did that op not stick" -- and whenever an op reports ok but the result
  is not there. Carries verified copy-paste recipes, the list of things that waste
  time on this build, and the workaround for each.
---

# ADT capabilities — measured on fm-cli 0.7.0 (29823677)

Generated from `fm-ADT-testing/tests/` on 2026-09-16T15:24:34. **Do not hand-edit**:
re-run the suite and `python3 tests/export_skill.py` to refresh it.

Every line here came from executing the CLI against a throwaway file. If a
recipe is in this skill, it passed on this build; if something is on the block
list, it failed on this build.

## Use it in this order

1. **About to author fm ops?** Check
   [references/NOT-SUPPORTED.md](references/NOT-SUPPORTED.md) first. If the
   thing is listed, say so and offer the workaround instead of attempting it.
2. **Need the working shape?** Copy it from
   [references/COOKBOOK.md](references/COOKBOOK.md) — 64 verified
   recipes.
3. **Answering "can it do X?"** Look up the capability key in
   [references/capabilities.json](references/capabilities.json): each entry
   carries `status` (`works` / `broken` / `unsupported` / `unknown`), the tier
   it reached, and a workaround where one exists.

## The state of this build

- **301 capabilities verified working**, 0 broken,
  39 confirmed absent.
- The CLI declares **218 script steps**
  (100.0% of FileMaker's own roster), so the
  script surface is essentially complete. **The real limits are in the layout
  surface.**

## The four things worth knowing before touching a layout

1. **`addObjects` takes 23 keys; `updateObjects` takes about 90.** An object's
   tooltip, icon, style, control type, value list, panel behaviour and
   accessibility CANNOT be set when it is created. Place it, read back the id
   from `createdObjectIds`, then configure it in a second op. Most "the CLI
   can't do X" turns out to be X asked for in the wrong place.

2. **Text-valued keys on a layout object are CALCULATIONS, not labels.**
   `tooltip`, `placeholderText`, `accessibilityTitle` and `hideCondition` are
   compiled, so a literal needs its own quotes inside the JSON string:
   `"tooltip": "\"Hello\""`. Bare prose is refused with DBError 106 because
   the engine reads it as field names.

3. **A calculation has three different shapes depending on where it sits.**
   Field options want an object `{"text": ..., "context": ...}` with
   `context` mandatory; `evaluate:calculation` wants a plain string with
   `context` as a SIBLING key; a layout object wants a bare string with no
   context at all.

4. **Bounds inside a container are relative to that container.** A child's
   `bounds` are measured from the parent's top-left, while a top-level
   object's are absolute on the layout. A portal row is the portal's height
   divided by `rows`, so always send `rows` together with `height` or the row
   height silently re-derives and the next inner-object edit is refused.

## Reading a result honestly

`status: "ok"` is weaker than it looks, in two specific ways this suite hit:

- **`validate:calculation` reports `status: "ok"` for an INVALID formula.**
  The question was answered; the answer is in `result.valid`. Branch on
  `result.valid`, never on `status`.
- **An op can be accepted and not deliver.** Confirm anything that matters
  with a read from a FRESH process — same-run reads can show state a later
  op rolls back.

## What this skill cannot tell you

Whether an object actually DRAWS. Nothing in ADT renders a native layout, so
"it is on disk" and "the user can see it" are different claims. Two open cases
need pixels: whether button-bar segments draw (their zero-bounds readback is a
reporting artifact, not a defect) and whether plain buttons draw at all
(quirk 73). Use the ADT Helper plug-in and `tests/visual.py` for that.

See also: `adt-quirks` for the full catalogue of edges and how each was found.
