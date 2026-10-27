---
name: app-icon
description: Make an app icon for a Mac or iOS app, from drafts to the files the build uses: a sheet of options drafted by Codex through Ringer (or the user's own artwork), then the macOS tile, the iOS asset-catalog icon and website favicons cut from the pick. Use when the user says "make an icon", "app icon", "icon options", "use this artwork as the icon", or a new app has no icon yet.
---

# App icon

Read the `app-support` notebook first: earlier apps' icon style and any lesson about icons.

## 1. Artwork

The artwork is one **square, full-bleed** image, 1024 px or larger, with nothing important within about 10% of the
edges (iOS masks the corners; the macOS tile is cut from the middle).

- **The user has artwork:** use it. Keep the original as `icon/AppIcon-source.png` in the app folder.
- **Drafts:** ask Codex for them through Ringer (load the `ringer` skill for how to dispatch; never call Codex
  inline). Ask for four to six distinct directions, each saved as its own square PNG under the app folder's
  `icon/drafts/`, from a brief that says what the app does, one visual idea per draft, flat or softly lit shapes
  that read at 32 px, no text or tiny detail, and full-bleed artwork (no rounded corners or drop shadow drawn in:
  the script below adds the shape). Show the drafts side by side (a contact sheet image or an HTML page) and let the
  user pick or steer; iterate on the pick rather than starting over.

Drafts are throwaway: commit only the chosen source and the generated icons, and delete `icon/drafts/` once picked.

## 2. Cut it for each platform

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/make-icons.py icon/AppIcon-source.png --mac icon/AppIcon.png          # Mac
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/make-icons.py icon/AppIcon-source.png \
  --ios Resources/Assets.xcassets/AppIcon.appiconset                                                         # iOS
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/make-icons.py icon/AppIcon-source.png --web <site folder>              # web
```

(Needs Pillow: `pip3 install pillow`.) What it encodes, so nobody relearns it:

- **macOS draws no mask.** The PNG is the rounded tile itself, 824 px inside a 1024 canvas with a transparent margin
  (Apple's grid), so it sits right beside system icons. `make-app.sh` builds `AppIcon.icns` from `icon/AppIcon.png`
  with `sips` and `iconutil` on every build.
- **iOS masks the icon itself.** It gets the whole square, **opaque**: App Store Connect rejects an icon with an alpha
  channel. One 1024 px image in the asset catalog is enough (Xcode 14 and later make the rest). Dark and tinted
  variants are optional extra images in the same `.appiconset`.
- **The menu bar icon is not the app icon.** Use an SF Symbol that echoes it (`Image(systemName:)`), or a custom
  template image: black on transparent, about 18 pt tall, marked as a template so macOS tints it for light and dark.

## 3. Check it

Look at it at real sizes before calling it done: the Mac icon in the Dock and in Finder's list view (16 and 32 px),
the iOS icon on the simulator's home screen. If the idea vanishes at 32 px, simplify the artwork, not the script.

Record the choice (and any lesson) in the notebook.
