#!/usr/bin/env python3
"""Turn one square, full-bleed piece of artwork into the icons each platform wants.

    python3 make-icons.py ART.png --mac _mac/icon/AppIcon.png        # macOS: rounded tile, 824 px on a 1024 canvas
    python3 make-icons.py ART.png --ios _ios/Resources/Assets.xcassets/AppIcon.appiconset
    python3 make-icons.py ART.png --web site/                         # favicons and the apple-touch icon

The rules it carries:
- macOS draws no mask, so the PNG itself is the rounded tile: 824 x 824 inside a 1024 canvas, transparent around it
  (Apple's icon grid). make-app.sh turns that PNG into AppIcon.icns.
- iOS masks the icon itself, so it gets the whole square, opaque (App Store Connect rejects an icon with alpha),
  as one 1024 px image in the asset catalog.
Needs Pillow in the system python3 (pip3 install pillow).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit('make-icons.py: needs Pillow (pip3 install pillow)')

CANVAS = 1024
TILE = 824
# Corner radius of the macOS tile: close to the continuous corner Apple's templates draw at this size.
RADIUS = 185


def load(path: Path) -> Image.Image:
    art = Image.open(path).convert('RGBA')
    w, h = art.size
    if abs(w - h) > 1:
        side = min(w, h)
        print(f'note: {path.name} is {w}x{h}; using the centre {side}x{side}', file=sys.stderr)
        art = art.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
    if art.width < CANVAS:
        print(f'note: {path.name} is only {art.width} px; icons will be upscaled and may look soft', file=sys.stderr)
    return art


def mac_tile(art: Image.Image) -> Image.Image:
    # Supersample the mask so the corners are smooth.
    scale = 4
    mask = Image.new('L', (TILE * scale, TILE * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, TILE * scale - 1, TILE * scale - 1), RADIUS * scale, fill=255)
    mask = mask.resize((TILE, TILE), Image.LANCZOS)
    tile = art.resize((TILE, TILE), Image.LANCZOS)
    tile.putalpha(Image.composite(tile.getchannel('A'), Image.new('L', tile.size, 0), mask))
    canvas = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
    offset = (CANVAS - TILE) // 2
    canvas.paste(tile, (offset, offset), tile)
    return canvas


def ios_square(art: Image.Image, background: str) -> Image.Image:
    flat = Image.new('RGB', (CANVAS, CANVAS), background)
    sized = art.resize((CANVAS, CANVAS), Image.LANCZOS)
    flat.paste(sized, (0, 0), sized)
    return flat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('art', type=Path)
    parser.add_argument('--mac', type=Path, help='write the macOS tile PNG here')
    parser.add_argument('--ios', type=Path, help='write AppIcon.png and Contents.json into this .appiconset')
    parser.add_argument('--web', type=Path, help='write favicon-32.png, icon-64.png, icon-512.png, apple-touch-icon.png')
    parser.add_argument('--background', default='#FFFFFF', help='iOS: colour behind any transparent parts')
    args = parser.parse_args()
    if not (args.mac or args.ios or args.web):
        parser.error('say at least one of --mac, --ios, --web')
    art = load(args.art)

    if args.mac:
        args.mac.parent.mkdir(parents=True, exist_ok=True)
        mac_tile(art).save(args.mac)
        print(args.mac)
    if args.ios:
        args.ios.mkdir(parents=True, exist_ok=True)
        ios_square(art, args.background).save(args.ios / 'AppIcon.png')
        contents = {'images': [{'filename': 'AppIcon.png', 'idiom': 'universal', 'platform': 'ios',
                                'size': '1024x1024'}],
                    'info': {'author': 'xcode', 'version': 1}}
        (args.ios / 'Contents.json').write_text(json.dumps(contents, indent=2) + '\n')
        print(args.ios / 'AppIcon.png')
    if args.web:
        args.web.mkdir(parents=True, exist_ok=True)
        tile = mac_tile(art)
        for name, size, image in [('favicon-32.png', 32, tile), ('icon-64.png', 64, tile), ('icon-512.png', 512, tile),
                                  ('apple-touch-icon.png', 180, ios_square(art, args.background))]:
            image.resize((size, size), Image.LANCZOS).save(args.web / name)
            print(args.web / name)


if __name__ == '__main__':
    main()
