#!/usr/bin/env python3
"""Connect Codex to the shared library and Claude's active Matt Pocock skills."""
import argparse
import json
from pathlib import Path
import re
import tempfile

import yaml
from build_codex import install

ROOT = Path(__file__).resolve().parents[1]
MARKER = '.dc-workflow-build.json'
GENERATOR = 'dc-plugins/scripts/install_workflow.py'
START = '<!-- dc-codex-setup:start -->'
END = '<!-- dc-codex-setup:end -->'
LIBRARY_SKILLS = {'library': 'wiki-engine/library', 'build-swarm': 'agent-operations/build-swarm'}
REQUIRED_MATT = {'wayfinder', 'grilling', 'domain-modeling', 'prototype', 'research',
                 'to-spec', 'to-tickets', 'implement', 'tdd', 'code-review', 'diagnosing-bugs', 'handoff'}


def metadata(path):
    text = path.read_text()
    if not text.startswith('---\n') or '\n---' not in text[4:]:
        raise ValueError(f'{path}: missing YAML frontmatter')
    front = text[4:].split('\n---', 1)[0]
    try:
        parsed = yaml.safe_load(front)
    except yaml.YAMLError:
        front = re.sub(r'^description: (.+)$', lambda m: 'description: ' + json.dumps(m[1]), front, flags=re.M)
        try:
            parsed = yaml.safe_load(front)
        except yaml.YAMLError as e:
            raise ValueError(f'{path}: invalid YAML frontmatter') from e
    if not isinstance(parsed, dict) or not isinstance(parsed.get('name'), str) or not isinstance(parsed.get('description'), str):
        raise ValueError(f'{path}: frontmatter needs string name and description')
    return parsed


def sources(library, registry):
    library = library.expanduser().resolve()
    for name in ('CLAUDE.md', 'index.md', 'skills/index.md'):
        if not (library / name).is_file():
            raise ValueError(f'Missing shared library file: {library / name}')
    result = {name: library / 'skills' / relative / 'SKILL.md' for name, relative in LIBRARY_SKILLS.items()}
    state = json.loads(registry.read_text())
    entries = [e for e in state.get('plugins', {}).get('mattpocock-skills@mattpocock', []) if e.get('scope') == 'user']
    if len(entries) != 1:
        raise ValueError('Expected one active user installation of mattpocock-skills@mattpocock')
    entry = entries[0]
    matt = Path(entry['installPath']).expanduser().resolve()
    manifest = json.loads((matt / '.claude-plugin/plugin.json').read_text())
    if manifest.get('name') != 'mattpocock-skills' or manifest.get('version') != entry.get('version'):
        raise ValueError('Matt Pocock registry/manifest mismatch; finish the Claude update first')
    for relative in manifest['skills']:
        path = (matt / relative / 'SKILL.md').resolve()
        if not path.is_relative_to(matt):
            raise ValueError(f'Skill escapes its registered package: {relative}')
        name = metadata(path)['name']
        if name in result or not re.fullmatch(r'[a-z0-9-]+', name):
            raise ValueError(f'Duplicate or invalid skill name: {name}')
        result[name] = path
    if not REQUIRED_MATT <= result.keys():
        raise ValueError(f'Missing PM workflow skills: {sorted(REQUIRED_MATT - result.keys())}')
    for name, path in result.items():
        if not path.is_file() or not isinstance(metadata(path).get('description'), str):
            raise ValueError(f'Missing or invalid skill: {name}: {path}')
    if not (library / 'skills/agent-operations/build-swarm/scripts/loop.py').is_file():
        raise ValueError('Missing canonical build-swarm loop.py')
    return library, matt, manifest, result


def managed_text(original, content):
    if original.count(START) != original.count(END) or original.count(START) > 1:
        raise ValueError('Malformed setup markers; preserve file for manual review')
    block = START + '\n' + content.rstrip() + '\n' + END
    if START in original:
        before, rest = original.split(START, 1)
        _, after = rest.split(END, 1)
        return before + block + after
    return original + ('\n\n' if original and not original.endswith('\n\n') else '') + block + '\n'


def write_managed(path, content):
    if path.is_symlink():
        raise ValueError(f'Refusing to write managed instructions through symlink: {path}')
    original = path.read_text() if path.exists() else ''
    updated = managed_text(original, content)
    if updated != original:
        path.parent.mkdir(parents=True, exist_ok=True)
        if original:
            backup = path.with_name(path.name + '.before-dc-setup')
            if not backup.exists():
                backup.write_text(original)
        path.write_text(updated)
    return path


def connect_agents(library, codex_home=None):
    codex_home = codex_home or Path.home() / '.codex'
    # Validate both contents before changing either file.
    paths = {
        library / 'AGENTS.md': '''# Shared library in Codex

Read `CLAUDE.md` here for the shared library schema, boundaries, and routing.
That file is the canonical instruction set for both IDEs. Claude tool names mean
available equivalent Codex tools. Resolve relative procedure links from their
source skill directories. For Ringer and cross-review, prefer the installed
Codex `ringer` and `cross-review-gate` skills, which adapt the host mechanics.

Before synchronizing, inspect Git status. With a clean tree, use `git pull --ff-only`.
With local edits, preserve them and read the current copy; do not stash, reset,
commit somebody else's changes, or pull through them. Commit only task-owned
library edits; a read-only lookup does not require a commit or push.''',
        codex_home / 'AGENTS.md': f'''# DataCraft shared workflow

The shared craft library is `{library}`. For prior research, reusable procedures,
or library queries and updates, load the installed `library` skill and read the
relevant source pages before researching from scratch. Keep client facts in the
client project. The library's schema applies to library work, not every repo.

For DataCraft PM work, use `pm` with the installed workflow skills (`wayfinder`,
`grilling`, `to-spec`, `to-tickets`, `implement`, `tdd`, `code-review`) as the work
requires. Existing project instructions and the user's scope govern which stages
apply; trivial changes do not need the whole chain.

Use the installed `ringer` skill for delegated model work. Codex-led technical
grilling uses Fable; Claude-led grilling retains Astra. The cross-review panel is
Astra + Fable. `build-swarm` uses the canonical library loop, outside Dropbox for
runtime state, with wave 1 as its default. Existing authorization persists.

Use `dc-setup` to check or refresh this integration. Plugin and connection changes
are picked up in new Codex tasks. Preserve hand edits and unrelated settings.'''
    }
    for path, content in paths.items():
        if path.is_symlink():
            raise ValueError(f'Refusing symlink: {path}')
        managed_text(path.read_text() if path.exists() else '', content)
    return [write_managed(p, c) for p, c in paths.items()]


def build(library, registry, output):
    library, matt, upstream, selected = sources(library, registry)
    dest = output / 'dc-workflow'
    if dest.exists():
        if dest.is_symlink() or not (dest / MARKER).is_file() or json.loads((dest / MARKER).read_text()).get('generator') != GENERATOR:
            raise ValueError(f'Refusing to replace unowned destination: {dest}')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.workflow-', dir=output) as tmp:
        stage = Path(tmp) / 'dc-workflow'
        for name, source in selected.items():
            desc = ' '.join(metadata(source)['description'].split())
            if name == 'build-swarm':
                desc = 'Execute a DataCraft PM ticket frontier through the canonical Ringer build loop, one ticket per wave by default. Use for build-swarm or a frontier with committed acceptance checks; parallel waves require the parallel-safety screen.'
            if len(desc) > 1000:
                desc = desc[:997].rsplit(' ', 1)[0] + '…'
            body = f'''# {name} in Codex

Read and follow the canonical skill at [{name}]({source}) for this task.
Read its referenced files relative to `{source.parent}`. The source remains
shared with Claude Code; do not create a separate copy of its knowledge or scripts.
If the source is missing after a Claude update, run the `dc-setup` refresh first.

Use Codex's available tools for Claude tool names; read a named skill's SKILL.md
when there is no Skill tool. Prefer the project's AGENTS.md, and also read its
shared CLAUDE.md when it carries the conventions. For model delegation load the
installed `ringer` skill; Codex-native subagent syntax is not a substitute for
Ringer in this workflow. Existing authorization and user instructions take precedence.
'''
            if name == 'library':
                body += f'''
Library root: `{library}`. Read its AGENTS.md and CLAUDE.md when working in it.
The AGENTS.md synchronization rule refines the source's blanket pull instruction:
inspect status first, pull --ff-only only when clean, and preserve local changes.
A lookup does not authorize committing or pushing unrelated library edits.
For skill discovery read skills/index.md. For a specific topic search relevant
index entries and pages rather than loading the entire library. Use pm-scaffold
for a DataCraft PM project; library/scaffolding procedures apply when requested.
'''
            if name == 'build-swarm':
                body += f'''
Use `{source.parent}/scripts/loop.py` in place of the source's
~/.claude/skills/build-swarm/scripts/loop.py examples. Supporting scripts and
references stay in that same canonical directory. The executable loop supports
one or more tickets at wave 1; the two-independent-ticket rule applies to parallel
waves. PM's current WORKFLOW.md binds the sequential loop for a ticket frontier.
Resolve the Ringer clone through the installed Ringer bridge and set RINGER_HOME
to that root before launching the loop if it differs from the default location.
Read the loop's --help before using it. Its --dry-run can park and commit tickets;
use a scratch repository for setup checks, not a user's active tracker.
'''
            if name in {'grilling', 'grill-me', 'to-tickets', 'wayfinder'}:
                body += '\nFor DataCraft PM grilling, load fast-grill first: Fable reviews technical recommendations from a Codex lead. Apply its accepted-agreement procedure to technical splits; taste and irreversible decisions retain the human boundary.\n'
            folder = stage / 'skills' / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('---\n' + yaml.safe_dump({'name': name, 'description': desc}, sort_keys=False) + '---\n\n' + body)
        folder = stage / 'skills/dc-setup'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text(f'''---
name: dc-setup
description: Check or refresh Joe's shared Claude Code and Codex plugin setup, library routing, PM workflow dependencies, Ringer bridge, and Claris adapters.
---

# DataCraft setup

Source checkout: `{ROOT}`. From any working directory:

- Read-only connection report: `python3 "{ROOT}/scripts/refresh_codex.py" --check`
- Refresh generated Codex plugins and managed library routing: `python3 "{ROOT}/scripts/refresh_codex.py" --install`

The refresh uses the current tracked DataCraft files, the shared library, and
Claude's active registered Claris and Matt Pocock installations. It does not pull
Git repos, update Claude plugins, run models, or change credentials. Report any
failure; do not claim later steps ran. New tasks pick up refreshed skills/tools.
''')
        description = 'Shared library access and Matt Pocock workflow skills for DataCraft PM in Codex.'
        manifest = {'name': 'dc-workflow', 'version': '0.1.0', 'description': description,
                    'author': {'name': 'DataCraft Development'}, 'skills': './skills/',
                    'interface': {'displayName': 'DataCraft Shared Workflow', 'shortDescription': description,
                                  'longDescription': description, 'developerName': 'DataCraft Development',
                                  'category': 'Productivity', 'capabilities': [],
                                  'defaultPrompt': ['Check the library for prior work.', 'Check my Codex setup.']}}
        (stage / '.codex-plugin').mkdir()
        (stage / '.codex-plugin/plugin.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / 'SOURCES.md').write_text(f'# Canonical sources\n\nLibrary: {library}\n\nMatt Pocock skills {upstream["version"]}: {matt}\nOriginal author: Matt Pocock. License: MIT. Procedures are read from that installed package; they are not vendored here.\n')
        (stage / MARKER).write_text(json.dumps({'generator': GENERATOR, 'library': str(library), 'matt': str(matt),
                                              'mattVersion': upstream['version'], 'sources': {n: str(p) for n,p in selected.items()}}, indent=2) + '\n')
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
    print(f'Built dc-workflow: {len(selected) + 1} skill entrypoints at {dest}')
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=ROOT.parents[1] / 'library')
    parser.add_argument('--registry', type=Path, default=Path.home() / '.claude/plugins/installed_plugins.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--plugin-creator-dir', type=Path, default=Path.home() / '.codex/skills/.system/plugin-creator')
    args = parser.parse_args()
    if args.install and args.output:
        parser.error('--install and --output cannot be combined')
    output = Path.home() / 'plugins' if args.install else args.output or ROOT / '.codex-build'
    package = build(args.library, args.registry, output.resolve())
    if args.install:
        install([package], args.plugin_creator_dir)
        connect_agents(args.library.expanduser().resolve())


if __name__ == '__main__':
    main()
