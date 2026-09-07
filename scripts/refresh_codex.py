#!/usr/bin/env python3
"""Build/refresh the DataCraft Codex setup, or report its local connection status."""
import argparse
import json
from pathlib import Path
import socket
import shutil
import tempfile
import subprocess
import sys

from build_codex import ROOT, PLUGINS, build_one, install
from install_ringer import build as build_ringer
from install_claris import resolve_sources, build as build_claris
from install_workflow import build as build_workflow, sources as workflow_sources, connect_agents


def connection_report(library, registry, cache):
    issues = []
    selected = None
    matt = None
    claris = {}
    try:
        _, _, matt, selected = workflow_sources(library, registry)
        print(f'Library: {library} ({len(selected)} canonical workflow skill sources found)')
        print(f'Matt Pocock: active Claude version {matt["version"]}')
    except (OSError, ValueError, KeyError) as e:
        issues.append(str(e))
    try:
        claris = resolve_sources(cache, registry)
        print('Claris: ' + ', '.join(f'{n} {m["version"]}' for n, (_, m) in claris.items()))
    except (OSError, ValueError, KeyError) as e:
        issues.append(str(e))
    try:
        result = subprocess.run(['codex', 'plugin', 'list', '--marketplace', 'personal', '--json'], capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Codex plugin inventory failed: ' + result.stderr.strip())
        installed = json.loads(result.stdout)['installed']
        if not isinstance(installed, list):
            raise ValueError('Codex plugin inventory has no installed list')
        expected = set(PLUGINS) | {'ringer', 'dc-workflow', 'filemaker-agentic-development', 'adt-standards-default'}
        for item in installed:
            if item['name'] in expected:
                print(f'Plugin: {item["name"]} {item["version"]} enabled={item["enabled"]}')
                issues.extend(installed_source_issues(item, library, matt, selected, claris))
        enabled = {x['name'] for x in installed if x['enabled']}
        issues.extend(f'Plugin missing or disabled: {x}' for x in sorted(expected - enabled))
    except (OSError, ValueError, KeyError, TypeError) as e:
        issues.append('Cannot inspect Codex plugins: ' + str(e))
    for path in [library / 'AGENTS.md', Path.home() / '.codex/AGENTS.md']:
        if not path.is_file() or '<!-- dc-codex-setup:start -->' not in path.read_text():
            issues.append(f'Managed routing not connected: {path}')
    ringer = subprocess.run([sys.executable, str(ROOT / 'scripts/ringer_bridge.py'), '--print-root'], capture_output=True, text=True)
    if ringer.returncode:
        issues.append(ringer.stderr.strip())
    else:
        print('Ringer clone: ' + ringer.stdout.strip())
    with socket.socket() as sock:
        sock.settimeout(1)
        online = sock.connect_ex(('127.0.0.1', 1366)) == 0
    print('FileMaker/ADT local endpoint: ' + ('listening (database access not tested)' if online else 'offline; start ADT/FileMaker for database work'))
    print('Credential hook: check persisted trust with Codex /hooks; script tests alone do not prove runtime enforcement.')
    print('Claude Design/Granola: optional host integrations; not verified by this command.')
    for issue in issues:
        print('NEEDS ATTENTION: ' + issue)
    return 1 if issues else 0


def installed_source_issues(item, library, matt, selected, claris):
    name = item['name']
    source = item.get('source', {})
    if source.get('source') != 'local' or not source.get('path'):
        return [f'{name}: expected a local generated package; run --install']
    package = Path(source['path']).expanduser()
    issues = []
    try:
        manifest = json.loads((package / '.codex-plugin/plugin.json').read_text())
        if manifest.get('version') != item['version']:
            issues.append(f'{name}: generated package differs from installed version; run --install')
        if name == 'dc-workflow' and selected is not None:
            marker = json.loads((package / '.dc-workflow-build.json').read_text())
            expected = {n: str(p) for n, p in selected.items()}
            if (marker.get('sources') != expected or marker.get('library') != str(library)
                    or marker.get('mattVersion') != matt['version']):
                issues.append('dc-workflow: canonical sources changed since installation; run --install')
            missing = [n for n, p in marker.get('sources', {}).items() if not Path(p).is_file()]
            if missing:
                issues.append('dc-workflow: missing linked sources: ' + ', '.join(missing))
        if name in claris:
            path, upstream = claris[name]
            marker = json.loads((package / '.dc-claris-build.json').read_text())
            if marker.get('source') != str(path) or marker.get('upstreamVersion') != upstream['version']:
                issues.append(f'{name}: Claude source changed since installation; run --install')
    except (OSError, ValueError, KeyError, TypeError) as e:
        issues.append(f'{name}: cannot verify installed source metadata: {e}')
    return issues


def promote(packages, output, creator):
    """Validate the whole batch before touching live package folders."""
    ownership = {'pm': '.dc-codex-build.json', 'design-dc': '.dc-codex-build.json',
                 'fm-dc': '.dc-codex-build.json', 'ringer': '.dc-ringer-build.json',
                 'filemaker-agentic-development': '.dc-claris-build.json',
                 'adt-standards-default': '.dc-claris-build.json', 'dc-workflow': '.dc-workflow-build.json'}
    for package in packages:
        dest = output / package.name
        if dest.exists() and (dest.is_symlink() or not (dest / ownership[package.name]).is_file()):
            raise ValueError(f'Refusing to replace unowned destination: {dest}')
        # Claris launch paths must target final installed sources, not staging.
        mcp = package / '.mcp.json'
        if package.name == 'filemaker-agentic-development' and mcp.exists():
            data = json.loads(mcp.read_text())
            data['mcpServers']['adt-mcp']['command'] = str(dest / 'bin/adt')
            mcp.write_text(json.dumps(data, indent=2) + '\n')
        subprocess.run([sys.executable, str(creator / 'scripts/validate_plugin.py'), str(package)], check=True)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.dc-previous-', dir=output) as temp:
        backup = Path(temp)
        moved = []
        try:
            for package in packages:
                dest = output / package.name
                old = backup / package.name
                if dest.exists():
                    dest.rename(old)
                moved.append((dest, old))
                shutil.copytree(package, dest)
        except BaseException:
            for dest, old in reversed(moved):
                if dest.exists():
                    shutil.rmtree(dest)
                if old.exists():
                    old.rename(dest)
            raise
    return [output / p.name for p in packages]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--install', action='store_true', help='Refresh all generated Codex plugins and managed routing')
    mode.add_argument('--check', action='store_true', help='Read-only local connection report; does not call models')
    parser.add_argument('--library', type=Path, default=ROOT.parents[1] / 'library')
    parser.add_argument('--registry', type=Path, default=Path.home() / '.claude/plugins/installed_plugins.json')
    parser.add_argument('--claris-cache', type=Path, default=Path.home() / '.claude/plugins/cache/claris')
    parser.add_argument('--output', type=Path, help='Preview output, default .codex-build; incompatible with --install')
    parser.add_argument('--plugin-creator-dir', type=Path, default=Path.home() / '.codex/skills/.system/plugin-creator')
    args = parser.parse_args()
    if args.install and args.output:
        parser.error('--install and --output cannot be combined')
    library = args.library.expanduser().resolve()
    if args.check:
        return connection_report(library, args.registry, args.claris_cache)
    # Resolve all external dependencies before replacing any generated package.
    workflow_sources(library, args.registry)
    claris = resolve_sources(args.claris_cache, args.registry)
    output = (Path.home() / 'plugins' if args.install else args.output or ROOT / '.codex-build').resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dc-refresh-') as temporary:
        staging = Path(temporary)
        packages = [build_one(name, staging) for name in PLUGINS]
        packages.append(build_ringer(library / 'skills/agent-operations', staging))
        packages.extend(build_claris(name, source, manifest, staging) for name, (source, manifest) in claris.items())
        packages.append(build_workflow(library, args.registry, staging))
        packages = promote(packages, output, args.plugin_creator_dir.expanduser())
    if args.install:
        install(packages, args.plugin_creator_dir.expanduser())
        connect_agents(library)
        print('Refresh complete. Start a new Codex task to load the updated skills and tools.')
    else:
        print('Preview built. Use --install to refresh Codex and connect managed instructions.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
        print(f'Refresh stopped: {e}', file=sys.stderr)
        raise SystemExit(1)
