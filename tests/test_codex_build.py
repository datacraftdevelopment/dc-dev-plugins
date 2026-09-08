import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CodexBuildTests(unittest.TestCase):
    def test_build_preserves_sources_and_converts_entrypoints(self):
        sources = list(ROOT.glob('*/skills/*/SKILL.md'))
        before = {p: p.read_bytes() for p in sources}
        with tempfile.TemporaryDirectory(prefix='codex build ') as tmp:
            result = subprocess.run(
                ['python3', str(ROOT / 'scripts/build_codex.py'), '--output', tmp],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = Path(tmp)
            for name in ('pm', 'design-dc', 'fm-dc'):
                plugin = out / name
                manifest = json.loads((plugin / '.codex-plugin/plugin.json').read_text())
                self.assertEqual(manifest['name'], name)
                self.assertFalse(any(p.is_symlink() for p in plugin.rglob('*')))
                self.assertFalse((plugin / '.venv').exists())
                self.assertFalse((plugin / '.claude-plugin').exists())
                for p in (plugin / 'skills').glob('*/SKILL.md'):
                    content = p.read_text()
                    self.assertIn('name:', content)
                    self.assertNotIn('CLAUDE_PLUGIN_ROOT', content)
                    self.assertNotIn('$ARGUMENTS', content)
            fm = out / 'fm-dc'
            for name in ('fm-init', 'fm-status', 'fm-scaffold', 'fm-rollback', 'fm-docs-sync',
                         'fm-patch-builder', 'fm-xml-validator'):
                self.assertTrue((fm / 'skills' / name / 'SKILL.md').is_file())
            self.assertIn('MUST NOT synthesize', (fm / 'skills/fm-patch-builder/SKILL.md').read_text())
            self.assertTrue((fm / 'tools/patch/apply_patch.py').is_file())
            self.assertTrue((fm / 'templates/scaffold/AGENTS.md').is_file())
            self.assertIn('.codex-plugin/plugin.json',
                          (fm / 'skills/fm-scaffold/SKILL.md').read_text())
            pm = out / 'pm'
            self.assertTrue((pm / 'template/AGENTS.md').is_file())
            self.assertIn('AGENTS.md', (pm / 'skills/pm-scaffold/SKILL.md').read_text())
            grill = (pm / 'skills/fast-grill/SKILL.md').read_text()
            self.assertIn('engine `claude`, model `claude-fable-5`', grill)
            self.assertIn('cross-vendor reviewer for a Codex-led grill', grill)
            self.assertIn('--grill-template', grill)
            self.assertNotIn('gpt-6-astra', grill)
            self.assertNotIn('gpt-5.6-sol', grill)
            self.assertIn('**Fable seat** (`engine: claude, model: claude-fable-5`',
                          (pm / 'WORKFLOW.md').read_text())
            sync = (out / 'design-dc/skills/design-sync/SKILL.md').read_text()
            self.assertIn('If DesignSync is unavailable', sync)
            self.assertIn('PLUGIN_ROOT', (pm / 'hooks/hooks.json').read_text())
            # Exercise the declared Codex hook command and event shape in a path with spaces.
            fixture = out / 'hook fixture'
            fixture.mkdir()
            subprocess.run(['git', 'init', '-q', str(fixture)], check=True)
            (fixture / '.env').write_text('DUMMY=value\n')
            hook = json.loads((pm / 'hooks/hooks.json').read_text())
            command = hook['hooks']['PreToolUse'][0]['hooks'][0]['command']
            guard = subprocess.run(['bash', '-c', command], cwd=fixture,
                                   env={**os.environ, 'PLUGIN_ROOT': str(pm)},
                                   input=json.dumps({'hook_event_name': 'PreToolUse',
                                                     'tool_name': 'Bash', 'cwd': str(fixture),
                                                     'tool_input': {'command': 'git add .env'}}),
                                   capture_output=True, text=True)
            self.assertEqual(guard.returncode, 2, guard.stderr)
            self.assertIn('credential-guard: BLOCKED', guard.stderr)
            safe = subprocess.run(['bash', '-c', command], cwd='/',
                                  env={**os.environ, 'PLUGIN_ROOT': str(pm)},
                                  input=json.dumps({'cwd': str(fixture),
                                                    'tool_input': {'command': 'git add safe.txt'}}),
                                  capture_output=True, text=True)
            self.assertEqual(safe.returncode, 0, safe.stderr)
            session = subprocess.run(['python3', str(pm / 'scripts/session.py'),
                                      '--root', str(fixture), 'open', '--name', 'fixture',
                                      '--intent', 'Exercise the relocated PM session helper.'],
                                     cwd='/', capture_output=True, text=True)
            self.assertEqual(session.returncode, 0, session.stderr)
            self.assertTrue((fixture / json.loads(session.stdout)['path']).is_file())
            self.assertTrue((pm / 'skills/ship-acceptance/SKILL.md').is_file())
            # Bundled scripts must work after relocation, from an unrelated cwd.
            probe = subprocess.run(['python3', str(fm / 'skills/fm-dataapi/scripts/fm.py'), '--help'],
                                   cwd='/', capture_output=True, text=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in sources})

    def test_refuses_unowned_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'pm'
            target.mkdir()
            keep = target / 'mine.txt'
            keep.write_text('keep')
            result = subprocess.run(['python3', str(ROOT / 'scripts/build_codex.py'),
                                     '--output', tmp], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Refusing to replace unowned destination', result.stderr)
            self.assertEqual(keep.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
