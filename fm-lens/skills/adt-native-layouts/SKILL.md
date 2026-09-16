---
name: adt-native-layouts
description: >
  Use when building or editing NATIVE FileMaker layouts through the fm CLI —
  create:layout / update:layout, placing fields, labels, portals, tab controls, slide
  controls, popovers, button bars, buttons, web viewers; wiring script triggers,
  control styles, tooltips, hide conditions; layout geometry, anchors, bounds errors,
  container/parent nesting. Also use when a layout passes every structural check but
  looks wrong in FileMaker Pro (clipped text, invisible objects), when choosing field
  heights under Apex Blue, or when asked what fm can and cannot do on layouts (colors,
  fonts, parts, themes).
---

# Native layouts through fm — how far it goes, and where it lies to you

`create:layout` / `update:layout` place and edit **17 object types**: field,
label, portal, webViewer, group, line, rectangle, roundedRectangle, oval,
tabControl, tabPanel, popoverButton, slideControl, slidePanel, buttonBar,
button, graphic — plus layout folders/separators, per-layout themes, script
triggers at layout and object level, control styles (editBox, dropDownList,
popupMenu, checkboxSet, radioButtonSet, …), calc-driven settings (tooltip,
hideCondition, placeholderText), field behavior, icons/pictures, geometry with
anchors and stacking. Exact keys: `fm help layout create` /
`fm help layout update` on the machine — that help tree is the contract.

## The two-pass pattern that works

1. `create:layout` — geometry + structure: fields, labels, containers, inline
   one-level children, button actions.
2. `read:layout detail:true` — map real ids from `result.contents.objects`
   (**not** `result.objects`). `createdObjectIds` is NOT in input order — never
   map by counting.
3. `update:layout` — `updateObjects` for behaviors (control styles, triggers,
   anchors, calc settings) and `addObjects` with `parent:<id>` for container
   interiors.

Everything round-trips: reads return the same JSON dialect updates accept
(exceptions: `icon`/`picture` go in as paths, come back as ids/embedded data).

## Structural rules the validator enforces

- **Inline nesting is one level deep per op.** Portal + fields inline: fine.
  TabControl + panels inline: fine. Fields *inside* those panels: second op
  with `parent`. Popover contents: ALWAYS a second op (the popover object is
  auto-minted beside its button; its id arrives in `createdObjectIds`).
- **A field's auto-label costs ~208pt to the left** and counts in
  container-bounds checks — inside containers, leave room or pass `"label":""`.
- Buttons and actionable groups take an `action` of exactly one script step,
  same JSON vocabulary as script bodies.
- `update:layout` deliberately has **no "replace all contents"** — objects the
  CLI can't model (charts; see `unmodelledCount`) can't be recreated, so
  wholesale replacement is refused. `removeObjects` (takes `[{"id":n}]`
  objects) runs before `addObjects`, so one op can swap an object.
- `defaultPanel` is tab-controls-only; slide controls refuse it.

## Hard limits — what fm cannot do

- **No raw colors, fonts, fills, or padding on any object.** Cosmetics come
  from the theme and its named styles. **From ADT 0.7.0 the CLI can author
  themes** (`create:theme` / `update:theme`, CSS-like syntax, always derived
  from a base). Read `fm help theme-css` first. `css` replaces the whole
  stylesheet, and writing the same selector twice is refused, so edit the
  base's rules in place rather than appending overrides. Before 0.7.0: Apex
  Blue only, no theme or style creation.
- **Parts:** from 0.7.0, `parts` on `create:layout` and `addParts` /
  `removeParts` on `update:layout` build header, footer, sub-summary and the
  rest. `layout-print-setup` covers print columns, margins and row height.
  Size the layout with `baseWidth`/`bodyHeight`; 0.7.0 refuses
  `width`/`height`. Before 0.7.0: body only. Still out of reach: list and
  table view configuration and grid control.
- **File Options are outside the surface** (opening layout, window-open
  triggers, auto-login) — GUI-only.

## THE TRAP: structural pass ≠ rendered right

**Rule: send `theme` on the `update:layout` that adds objects** (or in any
later op on that layout), even when it names the theme the layout already
wears (`"theme": "Apex Blue"`). Without an fm theme assignment, **nothing
fm added draws**: not labels, not buttons, not button bars. The parts still
draw, so the layout looks empty rather than broken. With the assignment,
plain buttons and every button-bar segment draw fine. Both versions read
back identically through `read:layout` detail, so only a capture shows the
difference. Measured on ADT 0.7.0 with FileMaker Pro 26.0.1 (quirk 106;
this is very likely what was behind quirks 72/73). Not yet checked:
`create:layout` with `theme`, and builds before 0.7.0. Assign the theme there
too until someone captures it.

Field clipping is the other trap. The engine's bounds validation accepts
**any height** — and clipping is
invisible to every structural read. Measured Apex Blue minimums (from
screenshots, after four layouts shipped with every field clipped):

| Object | Minimum height |
|---|---|
| Single-line edit box / dropdown | **~30pt** (22–24 clips the glyphs) |
| Portal-row field | ~28pt |
| Radio-button set | ~26pt per stacked value (4 values ≈ 108pt) |

A layout that validates perfectly can render broken, and nothing in fm, the
MCP tools, or adt will tell you. **Close the loop with pixels**: FM Lens
plug-in's `FMLens_WindowSnapshot` renders the FileMaker window in-process to a
PNG (no Screen Recording permission) — fm-authored snapshot script, fired via
fmp URL, PNG read back by the agent, fix, recapture. Snapshot discipline:
capture the *frontmost* window rather than matching titles (leftover
same-named windows hijack matches — identical PNG byte sizes are the tell),
Resize-to-Fit before shooting, and never blindly navigate the frontmost window
(the MCP connector may be frontmost — guard card, see `adt-connections`).

Two render cautions from the field: never do active layout work on a `.fmp12`
inside Dropbox (sync serves version-skewed copies — objects blink in and out;
move the file out first), and treat any "object won't render" observation with
suspicion until reproduced on a clean non-Dropbox file, and until the theme
rule above has been ruled out. Full stories in `adt-quirks` (38, 47, 48).
