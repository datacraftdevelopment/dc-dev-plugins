#!/usr/bin/env python3
"""Build Codex editions from tracked Claude plugin sources; optionally install locally."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = '.dc-codex-build.json'
PLUGINS = {
    'pm': ('DataCraft PM', 'Outcome tickets, subagent orchestration, session handoffs, and delivery checks.'),
    'design-dc': ('DataCraft Design', 'Design handoffs, HTML artifacts, Excalidraw, and design-system workflows.'),
    'fm-dc': ('DataCraft FileMaker', 'FileMaker development, APIs, XML analysis, patching, and verification.'),
    'ui-test': ('DataCraft UI Tests', 'Run macOS UI tests with evidence receipts and independent verification.'),
    'basecamp-dc': ('DataCraft Basecamp', 'Optional Basecamp client workflows and verified close-out procedures.'),
}
# Local plugins with no Codex edition: sdlc installs Claude Code hooks into a repo's .claude/.
CLAUDE_ONLY = {'sdlc'}

RUNTIME = '''## Codex runtime

This skill is generated from the shared Claude Code source. Use Codex's available
file, shell, search, and question tools for the procedures below.

Resolve `PLUGIN_ROOT` from the absolute path of this loaded `SKILL.md`: it is
two directories above the skill directory (`<plugin>/skills/<skill>/SKILL.md`).
Set `PLUGIN_ROOT` to that verified absolute plugin path in each shell invocation
that uses it. Do not assume the shell provides it or resolve it from the user's
working directory. Quote all paths and derived variables such as `"$PT"`.
Relative references are relative to this skill file; bundled tools and templates
are relative to `PLUGIN_ROOT`. Never guess another installation's cache path.

Use the user's request as command arguments; placeholders in examples must be
replaced with actual, safely quoted values. Invoke other installed skills by name
or read their SKILL.md. Claude-style tool names mean the equivalent available
Codex capability, not literal tool calls. Agent procedures shipped here are
skills: if independent verification is required, delegate with that procedure
using an available subagent tool; if unavailable, report that limitation.

Check availability before depending on Ringer, other plugins, MCP connectors,
local knowledge libraries, browser automation, or native application tools.
Explain a missing dependency and continue any independent work. Keep genuine
product references such as Claude Design. When using Ringer from Codex, its
configured Codex review seat is independent but is not a cross-vendor review.
For Ringer-backed PM work, load the installed `ringer` skill first; for a gate,
load `cross-review-gate`. Their bridge resolves the existing Ringer clone and
its `local/templates/` kits. Do not look for `Agent/Ringer` inside the project.

'''

DESIGN_SYNC = '''## Capability requirement

If DesignSync is unavailable, explain that direct Claude Design synchronization
requires a session that exposes that tool. Prepare a local inventory, diff, or
handoff file for the requested components instead. Do not invent DesignSync
calls, assume the separate claude-design bridge is installed, or claim a remote
sync occurred. If the tool is available, read its current contract before using
the workflow below.

'''

SUCCESSION_HOST = '''# Host operations — Codex

Use the current Codex app tool contracts. Discover `list_projects`,
`create_thread`, `list_threads`, `read_thread`, `wait_threads`,
`send_message_to_thread` and `set_thread_archived` before relying on them.
CLI-only environments may lack these controls: preserve the prepared handoff and
report manual startup required. Do not substitute an untracked background CLI.

An explicit user request to continue in fresh sessions authorizes successor
creation within its stated scope/budget. Installation alone does not. Autonomous
workers use the existing Ringer/build-swarm path; `create_thread` is only for
replacing this orchestrator. Never fork the full conversation for succession.

Keep successors on the **ordinary session tier: Sol for Codex**. Astra and Fable
remain Ringer review seats; successor creation never promotes the interactive
orchestrator to a reviewer model. When `create_thread` can select the model, set
`model: gpt-5.6-sol`; preserve the user's explicit model choice when it differs.

Call `list_projects` and match the recorded checkout. This beta's explicit
same-checkout opt-in selects the saved project directly (`environment: { type: local }`)
rather than a fresh worktree. If the user has not authorized that environment,
resolve it before launch. Preserve the configured model unless the user requests
another. Use the [successor prompt](prompt.md), including the chain and launch
attempt. Obtain this task's actual ID from host context; do not guess from recency.

Reserve `launch` first; only `dispatch_allowed: true` permits the one
`create_thread` call. Set its title to include the attempt marker. Record the
returned `threadId` with `created`. A `clientThreadId` means queued setup, not a
usable task ID: preserve launching and reconcile the actual task through host
status before recording it. Never pass a clientThreadId where threadId is required.
Emit the app's created-task directive for the actual creation result as required
by its tool contract. Creation is not the successor's running acknowledgement.

Use bounded `wait_threads` calls and retained cursors for host progress; keep each
wait at most 60 seconds. Read the helper's status to see acknowledgement. A queued
result, host completion or a message alone does not grant checkout ownership.
On an uncertain create, inspect the exact attempt marker via host inventory and
task content; do not dispatch again until non-creation is actually established.

After the successor acknowledges, verify release of owned workers/servers, then
record `retire`. If the successor ended its turn while waiting, send it a concise
continuation on its existing task after retirement; never create a replacement
just to wake it. Finally use `set_thread_archived` for this predecessor when the
opt-in authorizes retirement. Archival is separate from process exit/RAM release;
report the observed facts. Without archive support, leave this task quiescent and
report closure unconfirmed. If recovery cannot establish the predecessor is
stopped, keep the successor waiting and present the one unresolved blocker.
'''


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def source_metadata(name):
    """Fingerprint exactly the tracked inputs used by this local adapter."""
    tracked = run('git', '-C', str(ROOT), 'ls-files', '-z', '--', name,
                  'scripts/build_codex.py', capture_output=True).stdout.split('\0')
    digest = hashlib.sha256()
    for filename in sorted(filter(None, tracked)):
        path = ROOT / filename
        if path.is_symlink():
            raise ValueError(f'Cannot fingerprint symlink: {path}')
        content = path.read_bytes()
        # Include executable permissions: hooks may otherwise look unchanged.
        for value in (filename.encode(), str(path.stat().st_mode & 0o111).encode(), content):
            digest.update(len(value).to_bytes(8, 'big'))
            digest.update(value)
    manifest = json.loads((ROOT / name / '.claude-plugin/plugin.json').read_text())
    return {'upstreamVersion': manifest['version'], 'sourceFingerprint': digest.hexdigest()}


def adapt(text):
    text = text.replace('${CLAUDE_PLUGIN_ROOT}', '${PLUGIN_ROOT}')
    text = text.replace('~/.claude/CLAUDE.md', '~/.codex/AGENTS.md')
    text = text.replace('CLAUDE.md', 'AGENTS.md')
    text = text.replace('current Claude Code conversation', 'current conversation')
    text = text.replace('Claude Code plan mode', 'the available planning workflow')
    text = text.replace("Claude's", "the lead agent's").replace('Claude:', 'Lead agent:')
    text = re.sub(r'/(?:pm|fm-dc|design-dc):([a-z0-9-]+)', r'$\1', text)
    return text.replace('$ARGUMENTS', '<user-supplied arguments>')


def adapt_fast_grill(text):
    text = re.sub(r'- \*\*Degraded mode, detected and stated out loud\.\*\*[^\n]+',
                  '- **Degraded mode, detected and stated out loud.** The timeout is ten minutes and '
                  'Ringer retries format failures once. On quota, auth, or model-availability failure, '
                  'report the failure and leave the technical questions pending; do not burn another '
                  'attempt into a known limit. Do not switch back to the lead vendor or choose a '
                  'different model without the user asking. If the user chooses no seat, mark each '
                  'ruling `(unseated)`. A repeated format failure also leaves questions unsettled.', text)
    text = text.replace(' at medium reasoning effort (the house cross-vendor seat; '
                        '`gpt-5.6-sol` when Astra is quota-blocked)',
                        ' (the cross-vendor reviewer for a Codex-led grill)')
    text = text.replace('engine `codex`, model `gpt-6-astra`',
                        'engine `claude`, model `claude-fable-5`')
    text = text.replace('Astra', 'Fable')
    text = text.replace('with Codex', 'with Claude').replace('(Codex quota)', '(Claude quota)')
    text = text.replace('a Codex call', 'a Claude call')
    return text


def skill_text(text, name):
    if not text.startswith('---\n'):
        raise ValueError(f'{name}: missing frontmatter')
    front, body = text[4:].split('\n---', 1)
    try:
        metadata = yaml.safe_load(front)
    except yaml.YAMLError:
        # Some Claude sources use unquoted, single-line descriptions with colons.
        repaired = re.sub(r'^description: (.+)$',
                          lambda m: 'description: ' + json.dumps(m.group(1)),
                          front, flags=re.MULTILINE)
        metadata = yaml.safe_load(repaired)
    description = ' '.join(str(metadata['description']).split())
    if name == 'fast-grill':
        description = adapt_fast_grill(description)
        body = adapt_fast_grill(body)
        body += '''

## Codex-led manifest

Load the `ringer` skill and use its installed `scripts/ringer_bridge.py --grill-template`
to emit the Fable variant of the shared grill template. Fill that emitted JSON's
placeholders for the current round, then lint and run it through Ringer. It pins
`engine: claude`, `model: claude-fable-5` and removes Codex-only reasoning flags.
Keep `KIT_DIR` pointed at the existing Ringer `local/templates/grill-review/` so
the same verdict checker applies. Do not run or edit the shared Astra template
directly: Claude-led sessions still use that original. The bridge belongs to the
Ringer plugin, not this PM plugin's `PLUGIN_ROOT`.
'''
    # Discovery metadata has a 1024-character budget; preserve full context below.
    extra = ''
    if len(description) > 1024:
        extra = '## Full scope\n\n' + description + '\n\n'
        description = description[:1000].rsplit(' ', 1)[0] + '…'
    metadata = {'name': name, 'description': adapt(description)}
    if name == 'fm-scaffold':
        body = body.replace('├── .claude-plugin/plugin.json',
                            '├── .codex-plugin/plugin.json         ← Codex manifest, same name/version\n'
                            '   ├── .claude-plugin/plugin.json')
        body += '''

For `--client-kit`, create both manifests around the same `skills/` directory.
Use the installed plugin's `.codex-plugin/plugin.json` as the schema example;
set the client's actual name, version, description, author, `skills: "./skills/"`,
and interface metadata. Omit optional apps, MCP, and assets unless supplied.
Give the client SKILL.md valid name/description frontmatter and resolve bundled
scripts relative to that skill, so the kit works in either host.
'''
    if name == 'design-sync':
        body = body.replace('Drive the **built-in DesignSync tool** (present in Claude Code sessions;',
                            'When available, drive the **DesignSync tool** (in supported Claude Code sessions;')
    return ('---\n' + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
            + '---\n\n' + RUNTIME + (DESIGN_SYNC if name == 'design-sync' else '')
            + adapt(extra + body.lstrip()))


def build_one(name, parent):
    dest = parent / name
    if dest.exists() and (dest.is_symlink() or not (dest / MARKER).is_file()):
        raise ValueError(f'Refusing to replace unowned destination: {dest}')
    tracked = run('git', '-C', str(ROOT), 'ls-files', '-z', '--', name,
                  capture_output=True).stdout.split('\0')
    with tempfile.TemporaryDirectory(prefix=f'.{name}-', dir=parent) as temporary:
        stage = Path(temporary) / name
        stage.mkdir()
        for filename in filter(None, tracked):
            source = ROOT / filename
            relative = source.relative_to(ROOT / name)
            if relative.parts[0] in {'.claude-plugin', '.claude'}:
                continue
            if source.is_symlink():
                raise ValueError(f'Cannot package symlink: {source}')
            if any(part in {'.venv', '__pycache__', '.pytest_cache', 'sandbox', '.DS_Store'}
                   for part in relative.parts):
                raise ValueError(f'Unexpected tracked development file: {source}')
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if not (stage / 'skills').is_dir():
            raise ValueError(f'{name}: no tracked skills')
        # Adapt only Markdown; Python engines, assets, and reference data stay byte-identical.
        for path in stage.rglob('*.md'):
            path.write_text(adapt(path.read_text()))
        workflow = stage / 'WORKFLOW.md'
        if name == 'pm' and workflow.is_file():
            workflow.write_text(workflow.read_text().replace(
                '**Astra seat** (`engine: codex, model: gpt-6-astra`',
                '**Fable seat** (`engine: claude, model: claude-fable-5`'))
        for path in list(stage.rglob('CLAUDE.md')):
            path.rename(path.with_name('AGENTS.md'))
        for path in (stage / 'skills').glob('*/SKILL.md'):
            path.write_text(skill_text(path.read_text(), path.parent.name))
        if name == 'pm':
            host = stage / 'skills/session-succession/host.md'
            if host.exists():
                host.write_text(SUCCESSION_HOST)
        for kind in ('commands', 'agents'):
            for path in (stage / kind).glob('*.md'):
                target = stage / 'skills' / path.stem / 'SKILL.md'
                if target.exists():
                    raise ValueError(f'{name}: skill name collision: {path.stem}')
                target.parent.mkdir(parents=True)
                target.write_text(skill_text(path.read_text(), path.stem))
        hooks = stage / 'hooks/hooks.json'
        if hooks.exists():
            # Codex documents Bash matcher and tool_input.command compatibility.
            hooks.write_text(hooks.read_text().replace('\\"${CLAUDE_PLUGIN_ROOT}/hooks/credential-guard.sh\\"',
                                                       'bash \\"${PLUGIN_ROOT}/hooks/credential-guard.sh\\"'))
        manifest = json.loads((ROOT / name / '.claude-plugin/plugin.json').read_text())
        display, description = PLUGINS[name]
        manifest['description'] = description
        manifest['skills'] = './skills/'
        manifest['interface'] = {
            'displayName': display, 'shortDescription': description,
            'longDescription': description, 'developerName': 'DataCraft Development',
            'category': 'Productivity', 'capabilities': [],
            'defaultPrompt': ['Help me use ' + display + '.'],
        }
        digest = hashlib.sha256()
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                digest.update(str(path.relative_to(stage)).encode())
                digest.update(path.read_bytes())
        manifest['version'] = manifest['version'].split('+')[0] + '+codex.' + digest.hexdigest()[:12]
        manifest_path = stage / '.codex-plugin/plugin.json'
        manifest_path.parent.mkdir()
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / MARKER).write_text(json.dumps({
            'generator': 'dc-plugins/scripts/build_codex.py', **source_metadata(name)}) + '\n')
        if dest.exists():
            backup = Path(temporary) / 'previous'
            dest.rename(backup)
            try:
                stage.rename(dest)
            except BaseException:
                backup.rename(dest)
                raise
        else:
            stage.rename(dest)
    print(f'Built {name}: {len(list((dest / "skills").glob("*/SKILL.md")))} skills at {dest}')
    return dest


def install(packages, creator):
    helpers = creator / 'scripts'
    for filename in ('create_basic_plugin.py', 'validate_plugin.py', 'read_marketplace_name.py',
                     'update_plugin_cachebuster.py'):
        if not (helpers / filename).is_file():
            raise ValueError(f'Missing Codex plugin-creator helper: {helpers / filename}')
    marketplace = Path.home() / '.agents/plugins/marketplace.json'
    if marketplace.exists():
        run('python3', str(helpers / 'read_marketplace_name.py'))
    for package in packages:
        run('python3', str(helpers / 'validate_plugin.py'), str(package))
    existing = json.loads(marketplace.read_text())['plugins'] if marketplace.exists() else []
    for package in packages:
        entry = next((e for e in existing if e.get('name') == package.name), None)
        if entry:
            expected = {'source': 'local', 'path': f'./plugins/{package.name}'}
            if entry.get('source') != expected:
                raise ValueError(f'{package.name}: personal entry points at another source')
            # Preserve the existing catalog policy, ordering, and display metadata.
            run('python3', str(helpers / 'update_plugin_cachebuster.py'), str(package))
        else:
            # Scaffold handles personal catalog creation; restore our richer manifest.
            manifest = package / '.codex-plugin/plugin.json'
            content = manifest.read_bytes()
            try:
                run('python3', str(helpers / 'create_basic_plugin.py'), package.name,
                    '--path', str(package.parent), '--with-marketplace', '--force')
            finally:
                manifest.write_bytes(content)
        market_name = run('python3', str(helpers / 'read_marketplace_name.py'),
                          capture_output=True).stdout.strip()
        run('codex', 'plugin', 'add', f'{package.name}@{market_name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Build directory (default: .codex-build)')
    parser.add_argument('--install', action='store_true', help='Build into ~/plugins and install in Codex')
    parser.add_argument('--plugin', action='append', choices=list(PLUGINS),
                        help='Build only this plugin (repeat to select several)')
    parser.add_argument('--plugin-creator-dir', type=Path,
                        default=Path.home() / '.codex/skills/.system/plugin-creator')
    args = parser.parse_args()
    if args.install and args.output:
        parser.error('--install uses ~/plugins; do not combine it with --output')
    parent = (Path.home() / 'plugins' if args.install else args.output or ROOT / '.codex-build').resolve()
    parent.mkdir(parents=True, exist_ok=True)
    # Check all ownership constraints before replacing any package.
    selected = list(dict.fromkeys(args.plugin or PLUGINS))
    for name in selected:
        target = parent / name
        if target.exists() and (target.is_symlink() or not (target / MARKER).is_file()):
            raise ValueError(f'Refusing to replace unowned destination: {target}')
    packages = [build_one(name, parent) for name in selected]
    if args.install:
        install(packages, args.plugin_creator_dir.expanduser())


if __name__ == '__main__':
    main()
