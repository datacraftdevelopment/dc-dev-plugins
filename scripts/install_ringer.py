#!/usr/bin/env python3
"""Package the canonical Ringer and cross-review-gate skills for local Codex use."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

from build_codex import install

ROOT = Path(__file__).resolve().parents[1]
MARKER = '.dc-ringer-build.json'
SKILLS = ('ringer', 'cross-review-gate')

RUNTIME = '''## Running from Codex

Resolve `PLUGIN_ROOT` from this loaded SKILL.md's absolute path:
`<plugin>/skills/<skill>/SKILL.md`. Do not resolve it from the project cwd.
The plugin uses the existing Ringer clone and its existing configured engines;
it does not copy the engine, local configuration, credentials, or run history.

```bash
# Set PLUGIN_ROOT to the verified installed plugin directory first.
RINGER_ROOT="$(python3 "${PLUGIN_ROOT}/scripts/ringer_bridge.py" --print-root)"
python3 "${PLUGIN_ROOT}/scripts/ringer_bridge.py" --no-self-update --help
```

The bridge defaults to `~/Agentic-Mini/_Core/Ringer`; set `RINGER_ROOT` in
the environment if the clone lives elsewhere. All clone-relative paths below
(`README.md`, `templates/`, `local/`, `docs/`) are under `RINGER_ROOT`, not the
plugin or the current project. The existing `ringer` command on PATH is also
usable; `./ringer.py` examples mean the bridge above from an arbitrary cwd.
Keep each manifest's paths absolute so execution stays in its specified repo.

Use Codex shell execution for Ringer, retain the session ID for a running
process, and poll for its exit status while reporting progress. Use the app's
file-opening tool to show Ringer's artifact library/report HTML when available.
The cross-review panel kit is `${RINGER_ROOT}/local/templates/adversarial-review-panel/`;
the PM grill kit is `${RINGER_ROOT}/local/templates/grill-review/`.
For a Codex-led grill, run this bridge with `--grill-template` to emit the Fable
variant (`engine: claude`, `model: claude-fable-5`, no Codex reasoning flags).
Fill that emitted manifest, then lint and run it. The shared kit remains the
Astra version for Claude-led grilling; the two-seat review panel stays unchanged.
Read their README and manifest templates before composing a run. Check required
engine executables/configuration without printing secrets. Never run
`ringer install-agent`: it can overwrite the canonical Claude skill through a symlink.

An explicit request to run a gate already authorizes that dispatch; do not ask
again. Installing these skills alone does not request a review run. Preserve the
scope, consent, quota, verification, and Hold rules in the canonical procedure.
Use an already authorized model choice or the user's configured workflow seats;
request a choice when none exists. Do not claim that CLI checks prove live engine
authentication or model availability.

'''

DISPATCH = '''## Dispatch mechanics in Codex

Load the `ringer` skill and use the Ringer panel path below. This host does not
need Claude Code's openai-codex plugin or its companion script. Require a Git
repository, the existing Ringer clone, and configured/authenticated `codex` and
`claude` worker lanes. If a lane is unavailable, report the missing dependency
before changing the requested panel; do not silently call another engine.

From a Codex orchestrator, the **Claude seat provides cross-vendor detection**;
the Codex seat provides an independent fresh context in the same vendor family.
Both seats keep the canonical model pins below. Same-family findings from the
Codex seat deserve the anchoring scrutiny that the Claude seat gets when Claude
is orchestrating. A two-Codex run is not cross-vendor review.

'''


def convert(text, name):
    front, body = text[4:].split('\n---', 1)
    metadata = yaml.safe_load(front)
    description = ' '.join(metadata['description'].split())
    if name == 'cross-review-gate':
        description = description.replace('Requires a git repository and the openai-codex plugin with an authenticated Codex CLI.',
                                          'Requires a Git repository and Ringer with authenticated Codex and Claude worker lanes.')
        body = body.replace('Codex adversarially reviews the current artifact, Claude\ntriages',
                            'Independent Codex and Claude seats review the current artifact; the orchestrator\ntriages')
        body = re.sub(r'- Preconditions:.*?(?=\n- \*\*A dispatch)',
                      '- Preconditions: a Git repo and Ringer with configured/authenticated reviewer lanes.\n',
                      body, flags=re.DOTALL)
        body = re.sub(r'## Dispatch mechanics \(proven path\).*?(?=## Dispatch via Ringer)',
                      DISPATCH, body, flags=re.DOTALL)
        body = body.replace('prefer\nit over the companion script', 'use\nits two-seat panel')
        body = body.replace('Why: the companion-script job is a dark background task — temp-dir state,\n'
                            'the task output the only record. A Ringer run gives', 'A Ringer run gives')
        body = body.replace('— cross-vendor detection: different\n  training, different blind spots.',
                            '— independent fresh-context detection from the Codex family.')
        body = body.replace('— fresh-context detection. Same\n  family as the orchestrator but zero conversation context:',
                            '— cross-vendor detection from Claude, also with zero conversation context:')
        body = body.replace('the\n  weights match, so the delta is your anchoring',
                            'the\n  vendor differs, so the delta may expose different blind spots')
        body = body.replace('Claude-seat-only findings still earn extra scrutiny\n(shared family priors).',
                            'Codex-seat-only findings still earn extra scrutiny\n(shared family priors with the Codex orchestrator).')
        body = re.sub(r'## Relationship to installed tooling.*?(?=## Anti-patterns)',
                      '## Relationship to installed tooling\n\n'
                      'Ringer owns dispatch and logs. This skill owns triage and consensus.\n'
                      'Use receiving-code-review when available for verification discipline.\n'
                      'One review round per boundary unless the user asks for another.\n\n',
                      body, flags=re.DOTALL)
        body = body.replace("not Claude's to apply alone", "not the orchestrator's to apply alone")
    # Source links assumed the upstream .claude/skills/ringer location.
    body = re.sub(r'\[([^\]]+)\]\(\.\./\.\./\.\./templates/([^)]*)\)',
                  r'\1 (`${RINGER_ROOT}/templates/\2`)', body)
    return ('---\n' + yaml.safe_dump({'name': name, 'description': description},
                                    sort_keys=False, allow_unicode=True)
            + '---\n\n' + RUNTIME + body.lstrip())


def build(source, output):
    dest = output / 'ringer'
    if dest.exists() and (dest.is_symlink() or not (dest / MARKER).is_file()):
        raise ValueError(f'Refusing to replace unowned destination: {dest}')
    # Copy only the two explicit, tracked canonical skill files. No library recursion.
    contents = {}
    for name in SKILLS:
        path = source / name / 'SKILL.md'
        subprocess.run(['git', '-C', str(source), 'ls-files', '--error-unmatch',
                        f'{name}/SKILL.md'], check=True, capture_output=True)
        if path.is_symlink():
            raise ValueError(f'Expected canonical file, found symlink: {path}')
        contents[name] = path.read_text()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ringer-', dir=output) as tmp:
        stage = Path(tmp) / 'ringer'
        for name, text in contents.items():
            path = stage / 'skills' / name / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text(convert(text, name))
        (stage / 'scripts').mkdir()
        shutil.copy2(ROOT / 'scripts/ringer_bridge.py', stage / 'scripts/ringer_bridge.py')
        digest = hashlib.sha256()
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                digest.update(path.read_bytes())
        description = 'Ringer orchestration and cross-review gates for DataCraft PM workflows.'
        manifest = {'name': 'ringer', 'version': '0.1.0+codex.' + digest.hexdigest()[:12],
                    'description': description, 'author': {'name': 'DataCraft Development'},
                    'skills': './skills/', 'interface': {
                        'displayName': 'DataCraft Ringer', 'shortDescription': description,
                        'longDescription': description, 'developerName': 'DataCraft Development',
                        'category': 'Productivity', 'capabilities': [],
                        'defaultPrompt': ['Use Ringer for a cross-review gate.']}}
        (stage / '.codex-plugin').mkdir()
        (stage / '.codex-plugin/plugin.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / MARKER).write_text(json.dumps({'generator': 'dc-plugins/scripts/install_ringer.py',
                                             'skills': list(SKILLS)}) + '\n')
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
    print(f'Built Ringer: {len(SKILLS)} canonical skills at {dest}')
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=ROOT.parents[2] / '_Core/library/skills/agent-operations')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--plugin-creator-dir', type=Path,
                        default=Path.home() / '.codex/skills/.system/plugin-creator')
    args = parser.parse_args()
    if args.install and args.output:
        parser.error('--install uses ~/plugins; do not combine with --output')
    output = Path.home() / 'plugins' if args.install else args.output or ROOT / '.codex-build'
    package = build(args.source.expanduser().resolve(), output.expanduser().resolve())
    if args.install:
        install([package], args.plugin_creator_dir.expanduser())


if __name__ == '__main__':
    main()
