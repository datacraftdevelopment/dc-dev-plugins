#!/usr/bin/env python3
"""Copy the Mac or iOS app template into a repo, filling in the app's names.

    python3 new-app.py mac --repo . --name Notebook --display "Notebook" --bundle-id dev.example.notebook \
        --release-repo owner/notebook --owner "Example Ltd" [--window] [--dir _mac]
    python3 new-app.py ios --repo . --name Tally --display "Tally" --bundle-id dev.example.tally --team ABCDE12345 \
        [--dir _ios]

Refuses to write into a folder that already exists, so it never overwrites an app. Prints what it wrote.
"""
from __future__ import annotations

import argparse
import datetime
import re
import shutil
import stat
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
TEMPLATES = PLUGIN / 'templates'
TEXT_SUFFIXES = {'.swift', '.sh', '.md', '.yml', '.json', '.plist', '.env', ''}


def fail(message: str) -> None:
    print(f'new-app.py: {message}', file=sys.stderr)
    sys.exit(1)


def check(args: argparse.Namespace) -> None:
    if not re.fullmatch(r'[A-Z][A-Za-z0-9]*', args.name):
        fail('--name must be a Swift type name: letters and digits, starting with a capital (e.g. Notebook)')
    if any(c in args.display for c in '"\\$`'):
        fail('--display may not contain quotes, backslashes, $ or backticks')
    if not re.fullmatch(r'[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+', args.bundle_id):
        fail('--bundle-id must look like dev.example.app')
    if args.kind == 'mac' and not re.fullmatch(r'[\w.-]+/[\w.-]+', args.release_repo or ''):
        fail('--release-repo owner/repo is required for a Mac app (its GitHub releases carry the downloads)')
    if args.kind == 'ios' and not re.fullmatch(r'[A-Z0-9]{10}', args.team or ''):
        fail('--team is required for an iOS app: the ten-character Apple Developer team ID')


def fill(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def copy_tree(src: Path, dest: Path, values: dict[str, str], skip: set[str]) -> list[Path]:
    written = []
    for path in sorted(src.rglob('*')):
        rel = path.relative_to(src)
        if path.is_dir() or rel.name in skip:
            continue
        target = dest / fill(str(rel), values)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in TEXT_SUFFIXES or path.name in {'.gitignore', 'VERSION'}:
            target.write_text(fill(path.read_text(), values))
        else:
            shutil.copyfile(path, target)
        if path.suffix == '.sh':
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('kind', choices=['mac', 'ios'])
    parser.add_argument('--repo', default='.', help='the git repo the app goes into')
    parser.add_argument('--dir', help='folder inside the repo (default _mac or _ios)')
    parser.add_argument('--name', required=True, help='Swift type name, also the executable and asset name')
    parser.add_argument('--display', help='the name people see (default: --name)')
    parser.add_argument('--bundle-id', required=True)
    parser.add_argument('--release-repo', help='Mac: owner/repo whose GitHub releases carry the app')
    parser.add_argument('--owner', default='', help='copyright holder')
    parser.add_argument('--team', help='iOS: Apple Developer team ID')
    parser.add_argument('--window', action='store_true', help='Mac: a window app instead of a menu bar app')
    args = parser.parse_args()
    args.display = args.display or args.name
    check(args)

    repo = Path(args.repo).resolve()
    if not (repo / '.git').exists():
        fail(f'{repo} is not a git repo (git init first)')
    folder = args.dir or f'_{args.kind}'
    dest = repo / folder
    if dest.exists():
        fail(f'{dest} already exists; pick another --dir')

    values = {
        '__APP__': args.name,
        '__DISPLAY__': args.display,
        '__BUNDLE_ID__': args.bundle_id,
        '__REPO__': args.release_repo or '',
        '__TEAM__': args.team or '',
        '__OWNER__': args.owner,
        '__YEAR__': str(datetime.date.today().year),
        '__MENU_BAR__': '0' if args.window else '1',
        '__SPARKLE_ACCOUNT__': args.name.lower(),
        '__DIR__': folder,
        '__DIR_SLUG__': re.sub(r'[^a-z0-9]+', '-', folder.lower()).strip('-') or 'app',
    }

    if args.kind == 'mac':
        variant = 'App.window.swift' if args.window else 'App.menubar.swift'
        written = copy_tree(TEMPLATES / 'mac', dest, values, skip={'App.window.swift', 'App.menubar.swift'})
        app_swift = dest / 'Sources' / args.name / f'{args.name}App.swift'
        app_swift.write_text(fill((TEMPLATES / 'mac/Sources/__APP__' / variant).read_text(), values))
        written.append(app_swift)
        workflow = repo / '.github/workflows' / f"{values['__DIR_SLUG__']}.yml"
        if workflow.exists():
            print(f'note: {workflow} exists, so the CI workflow was not written', file=sys.stderr)
        else:
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(fill((TEMPLATES / 'mac-workflow/app.yml').read_text(), values))
            written.append(workflow)
    else:
        written = copy_tree(TEMPLATES / 'ios', dest, values, skip=set())

    left = [p for p in written if p.suffix in TEXT_SUFFIXES and re.search(r'__[A-Z_]+__', p.read_text())]
    if left:
        fail(f'placeholders left in {", ".join(str(p) for p in left)}')
    for path in written:
        print(path.relative_to(repo))


if __name__ == '__main__':
    main()
