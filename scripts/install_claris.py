#!/usr/bin/env python3
"""Refresh local Codex editions from Claude's active Claris plugin installations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import yaml

from build_codex import install

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('filemaker-agentic-development', 'adt-standards-default')
MARKER = '.dc-claris-build.json'
IGNORED = {'.DS_Store', '.in_use', '__pycache__', '.git', '.claude-plugin'}

RUNTIME = '''## Codex host integration

This is a local adaptation of the installed Claris plugin. Claris's procedure
below and its bundled references remain the authority. Read `AGENTS.md` in the
project. When ADT writes `.claude/skills/fm-cli/SKILL.md`, read that actual file
and its references directly; Codex can read it even though it is not an
automatically discovered Codex skill. Do not invent a different generated path.

Resolve `PLUGIN_ROOT` from this loaded file's absolute location:
`<plugin>/skills/<skill>/SKILL.md`. Before running the `adt` or `fm` examples,
set `PATH="${PLUGIN_ROOT}/bin:$PATH"` in that shell invocation, or call those
executables by their full plugin paths. Keep the working directory at the ADT
project so `adt.json` is found. The `adt-mcp` server is bundled with this plugin;
use the available MCP tool names in Codex rather than guessing a Claude prefix.

Use `adt standards` to resolve the project's chosen pack. Installing a standards
pack does not select it for a project. Preserve project overrides and per-file
enabled flags. The default pack's name is `default`, not its plugin identifier.
Do not replace working ADT commands with another FileMaker plugin's workflow.
Required FileMaker application/framework installations remain local dependencies.

'''

STANDARDS = '''---
name: adt-standards-default
description: Use when an ADT project declares the default FileMaker standards pack, or the user asks to inspect or adopt Claris's default naming and design conventions.
---

# Claris default standards pack

This plugin makes Claris's default pack available; it does not activate it for
every project. Load `filemaker-standards` from the FileMaker Agentic Development
plugin and run `adt standards` in the project first. ADT resolves the pack using
the existing Claris installation that supplied this local edition.

The project selects it with `"standards": { "pack": "default" }` in `adt.json`.
Only change that project setting when the user asks to adopt the pack. Preserve
existing per-file enabled flags and project overrides.

Read the actual paths ADT prints. The copied pack is also at `../../standards/`
relative to this SKILL.md. Apply its files using Claris's layering rules:

- `naming.md`: additive overrides over the toolkit baseline.
- `patterns.md`: a matching section replaces the baseline section in full.
- `advisory.md`: suggestions during review only; not generation constraints.
- `checks.json`: machine checks supplement prose; do not weaken them to pass.

When no pack is declared, the universal baseline applies. When the declared pack
is unavailable, report that once and follow the baseline as filemaker-standards
directs; do not silently force this pack or copy its rules into the project.
'''


def resolve_sources(cache, registry):
    state = json.loads(registry.read_text())
    sources = {}
    for name in NAMES:
        entries = [e for e in state.get('plugins', {}).get(name + '@claris', [])
                   if e.get('scope') == 'user']
        if len(entries) != 1:
            raise ValueError(f'No active user installation (or ambiguous entries) for {name}@claris')
        entry = entries[0]
        source = Path(entry['installPath']).expanduser().resolve()
        if not source.is_relative_to((cache / name).resolve()) or not source.is_dir():
            raise ValueError(f'{name}: registered source is missing or outside the supplied cache')
        manifest = json.loads((source / '.claude-plugin/plugin.json').read_text())
        if manifest.get('name') != name or manifest.get('version') != entry.get('version'):
            raise ValueError(f'{name}: registry and manifest disagree; finish the Claude update first')
        # Refuse new host integration surfaces until the adapter supports them explicitly.
        unsupported = {'hooks', 'commands', 'agents', 'settings', 'userConfig'} & manifest.keys()
        if unsupported or any((source / d).exists() for d in ('hooks', 'commands', 'agents', '.claude')):
            raise ValueError(f'{name}: new Claude integration surface requires adapter review')
        sources[name] = (source, manifest)
    return sources


def check_destination(dest):
    if dest.exists():
        if dest.is_symlink() or not (dest / MARKER).is_file():
            raise ValueError(f'Refusing to replace unowned destination: {dest}')
        if json.loads((dest / MARKER).read_text()).get('generator') != 'dc-plugins/scripts/install_claris.py':
            raise ValueError(f'Refusing to replace unowned destination: {dest}')


def build(name, source, original, output):
    dest = output / name
    check_destination(dest)
    with tempfile.TemporaryDirectory(prefix=f'.{name}-', dir=output) as tmp:
        stage = Path(tmp) / name
        stage.mkdir()
        digest = hashlib.sha256(Path(__file__).read_bytes())
        for path in sorted(source.rglob('*')):
            relative = path.relative_to(source)
            if any(part in IGNORED for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f'Cannot package a cache symlink: {path}')
            if path.is_file():
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                digest.update(str(relative).encode())
                digest.update(path.read_bytes())
        for skill in (stage / 'skills').glob('*/SKILL.md'):
            text = skill.read_text()
            if not text.startswith('---\n'):
                raise ValueError(f'{skill}: missing skill frontmatter')
            front, body = text[4:].split('\n---', 1)
            metadata = yaml.safe_load(front)
            skill.write_text('---\n' + yaml.safe_dump({k: metadata[k] for k in ('name', 'description')},
                                                     sort_keys=False, allow_unicode=True)
                             + '---\n\n' + RUNTIME + body.lstrip())
        if name == 'adt-standards-default':
            target = stage / 'skills/adt-standards-default/SKILL.md'
            target.parent.mkdir(parents=True)
            target.write_text(STANDARDS)
            # Keep the pack's slug metadata as well as the standards verbatim.
            meta = source / '.claude-plugin/META.json'
            if meta.is_file():
                shutil.copy2(meta, stage / 'META.json')
        manifest = {k: v for k, v in original.items() if k in {
            'name', 'version', 'description', 'author', 'homepage', 'license', 'keywords', 'repository'}}
        digest.update(json.dumps(original, sort_keys=True).encode())
        manifest['version'] = original['version'].split('+')[0] + '+codex.' + digest.hexdigest()[:12]
        manifest['skills'] = './skills/'
        manifest['interface'] = {
            'displayName': original.get('displayName', name) + ' (Local Codex)',
            'shortDescription': 'Local Codex edition of the installed Claris plugin.',
            'longDescription': original['description'], 'developerName': 'Claris · local Codex adaptation',
            'category': 'Productivity', 'capabilities': [],
            'defaultPrompt': ['Help me use ' + name + '.']}
        mcp_path = stage / '.mcp.json'
        if mcp_path.is_file():
            mcp = json.loads(mcp_path.read_text())
            servers = mcp.get('mcpServers', {})
            if set(servers) != {'adt-mcp'} or servers['adt-mcp'].get('command') != '${CLAUDE_PLUGIN_ROOT}/bin/adt':
                raise ValueError('Claris MCP launch contract changed; review before refreshing')
            # Absolute generated local path: stable across Codex cache/version directories.
            servers['adt-mcp']['command'] = str(dest / 'bin/adt')
            mcp_path.write_text(json.dumps(mcp, indent=2) + '\n')
            manifest['mcpServers'] = './.mcp.json'
        (stage / '.codex-plugin').mkdir()
        (stage / '.codex-plugin/plugin.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / MARKER).write_text(json.dumps({
            'generator': 'dc-plugins/scripts/install_claris.py', 'source': str(source),
            'upstreamVersion': original['version'], 'fingerprint': digest.hexdigest()}, indent=2) + '\n')
        if dest.exists():
            backup = Path(tmp) / 'previous'
            dest.rename(backup)
            try:
                stage.rename(dest)
            except BaseException:
                backup.rename(dest)
                raise
        else:
            stage.rename(dest)
    print(f'Built {name} from Claude active version {original["version"]}: {dest}')
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path.home() / '.claude/plugins/cache/claris')
    parser.add_argument('--registry', type=Path, default=Path.home() / '.claude/plugins/installed_plugins.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--plugin-creator-dir', type=Path,
                        default=Path.home() / '.codex/skills/.system/plugin-creator')
    args = parser.parse_args()
    if args.install and args.output:
        parser.error('--install uses ~/plugins; do not combine with --output')
    sources = resolve_sources(args.cache.expanduser().resolve(), args.registry.expanduser().resolve())
    output = (Path.home() / 'plugins' if args.install else args.output or ROOT / '.codex-build').resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        check_destination(output / name)
    packages = [build(name, *sources[name], output) for name in NAMES]
    if args.install:
        install(packages, args.plugin_creator_dir.expanduser())


if __name__ == '__main__':
    main()
