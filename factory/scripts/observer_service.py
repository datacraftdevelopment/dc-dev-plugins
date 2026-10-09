#!/usr/bin/env python3
"""Install/status/remove the scoped local observer; never operate Runway itself."""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path


def manifest(root, interval=30):
    output = root / '_pm/observer'
    return {'Label': 'com.joe.runway.observer.dc-dev-plugins',
            'ProgramArguments': [sys.executable,
                str(Path(__file__).with_name('observe.py').resolve()), '--root', str(root),
                '--interval', str(interval)], 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 30, 'StandardOutPath': str(output / 'service.log'),
            'StandardErrorPath': str(output / 'service-error.log')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'status', 'uninstall', 'preview'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--interval', default=30, type=int, choices=range(30, 61))
    args = parser.parse_args()
    root = args.root.resolve()
    data = manifest(root, args.interval)
    label = data['Label']
    target = f'gui/{os.getuid()}/{label}'
    path = Path.home() / 'Library/LaunchAgents' / f'{label}.plist'
    if args.action == 'preview':
        print(plistlib.dumps(data).decode())
    elif args.action == 'status':
        subprocess.run(['launchctl', 'print', target], check=True)
    elif args.action == 'install':
        if path.exists():
            raise SystemExit(f'Already configured: {path}. Inspect before replacing.')
        if not (root / 'runway.json').is_file():
            raise SystemExit('Expected runway.json in the approved target repo')
        (root / '_pm/observer').mkdir(parents=True, exist_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps(data))
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)], check=True)
        print(f'Installed {label}; local events only, no AI wake-up route.')
    else:
        subprocess.run(['launchctl', 'bootout', target], check=True)
        path.unlink()


if __name__ == '__main__':
    main()
