#!/usr/bin/env python3
"""Install/status/remove the scoped local observer; never operate Runway itself."""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path


def manifest(root, interval=600):
    return {'Label': 'com.joe.runway.observer.dc-dev-plugins',
            'ProgramArguments': [sys.executable,
                str(Path(__file__).with_name('observe.py').resolve()), '--root', str(root),
                '--interval', str(interval)], 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 30, 'StandardOutPath': '/dev/null',
            'StandardErrorPath': '/dev/null'}


def unload(target):
    def absent(result):
        return result.returncode == 113 and 'Could not find service' in result.stderr

    probe = subprocess.run(['launchctl', 'print', target], capture_output=True, text=True)
    if absent(probe):
        return
    if probe.returncode:
        raise subprocess.CalledProcessError(probe.returncode, probe.args,
                                            output=probe.stdout, stderr=probe.stderr)
    result = subprocess.run(['launchctl', 'bootout', target], capture_output=True, text=True)
    if result.returncode:
        # The service may disappear between print and bootout. Reconcile that
        # specific race; do not mask permission or domain errors.
        after = subprocess.run(['launchctl', 'print', target], capture_output=True, text=True)
        if not absent(after):
            raise subprocess.CalledProcessError(result.returncode, result.args,
                                                output=result.stdout, stderr=result.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'status', 'uninstall', 'preview', 'set-interval', 'refresh'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--interval', default=600, type=int, choices=range(30, 3601), metavar='SECONDS')
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
    elif args.action in ('set-interval', 'refresh'):
        existing = plistlib.loads(path.read_bytes())
        argv = existing['ProgramArguments']
        if existing.get('Label') != label or argv[argv.index('--root') + 1] != str(root):
            raise SystemExit('Existing observer scope differs; inspect configuration first')
        if args.action == 'set-interval':
            argv[argv.index('--interval') + 1] = str(args.interval)
        existing['StandardOutPath'] = '/dev/null'
        existing['StandardErrorPath'] = '/dev/null'
        unload(target)
        path.write_bytes(plistlib.dumps(existing))
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)], check=True)
        print(f'Observer {args.action} applied; Runway unchanged.')
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
        unload(target)
        path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
