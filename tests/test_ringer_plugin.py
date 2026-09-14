from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RingerPluginTests(unittest.TestCase):
    def test_host_conversion_preserves_scoped_agreement_authority(self):
        import importlib.util
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        spec = importlib.util.spec_from_file_location('ringer_install', ROOT / 'scripts/install_ringer.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = ('---\nname: cross-review-gate\ndescription: Test\n---\n'
                  '- Preconditions: legacy host setup.\n'
                  '- **A dispatch** follows the accepted scope.\n'
                  '## Execution-agreement mode (dc-autonomy-v1)\n'
                  'Require independent confirmation.\n'
                  '## Relationship to installed tooling\nLegacy host rules.\n'
                  '## Anti-patterns\nDo not exceed the accepted agreement.\n')
        converted = module.convert(source, 'cross-review-gate')
        self.assertIn('Require independent confirmation.', converted)
        self.assertIn('review.max_rounds', converted)
        self.assertNotIn('One review round per boundary unless the user asks for another.', converted)

    def test_packaged_policy_resources_are_tracked_and_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            for name in ('ringer', 'cross-review-gate'):
                skill = source / name / 'SKILL.md'
                skill.parent.mkdir()
                skill.write_text(f'---\nname: {name}\ndescription: Test skill\n---\n\n'
                                 '[Policy](references/policy.md)\n')
                ref = skill.parent / 'references/policy.md'
                ref.parent.mkdir()
                ref.write_text('Require independent confirmation.\n')
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
            (source / 'ringer/references/private-notes.md').write_text('must not ship\n')
            output = root / 'output'
            result = subprocess.run(['python3', str(ROOT / 'scripts/install_ringer.py'),
                                     '--source', str(source), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ('ringer', 'cross-review-gate'):
                copied = output / 'ringer/skills' / name / 'references/policy.md'
                self.assertTrue(copied.is_file(), f'Missing policy resource for {name}')
                self.assertEqual(copied.read_text(), 'Require independent confirmation.\n')
            self.assertFalse((output / 'ringer/skills/ringer/references/private-notes.md').exists())

    def test_tracked_resource_symlinks_do_not_escape_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            for name in ('ringer', 'cross-review-gate'):
                skill = source / name / 'SKILL.md'
                skill.parent.mkdir()
                skill.write_text(f'---\nname: {name}\ndescription: Test skill\n---\n\nTest\n')
            secret = root / 'outside.txt'
            secret.write_text('outside source\n')
            (source / 'ringer/leak.txt').symlink_to(secret)
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
            result = subprocess.run(['python3', str(ROOT / 'scripts/install_ringer.py'),
                                     '--source', str(source), '--output', str(root / 'output')],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('symlink', result.stderr.lower())

    def test_grill_template_uses_fable_without_changing_shared_kit(self):
        import json
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'ringer.py').write_text('')
            template = root / 'local/templates/grill-review/manifest.template.json'
            template.parent.mkdir(parents=True)
            original = {'tasks': [{'key': 'round-{{ROUND}}-astra', 'engine': 'codex',
                                  'model': 'gpt-6-astra', 'engine_args': ['-c', 'model_reasoning_effort=medium'],
                                  'spec': 'Review the questions', 'check': 'python3 check.py'}]}
            template.write_text(json.dumps(original))
            result = subprocess.run(['python3', str(ROOT / 'scripts/ringer_bridge.py'), '--grill-template'],
                                    env={**os.environ, 'RINGER_ROOT': tmp},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            task = json.loads(result.stdout)['tasks'][0]
            self.assertEqual((task['engine'], task['model']), ('claude', 'claude-fable-5'))
            self.assertEqual(task['key'], 'round-{{ROUND}}-fable')
            self.assertNotIn('engine_args', task)
            self.assertEqual(task['check'], original['tasks'][0]['check'])
            self.assertEqual(json.loads(template.read_text()), original)

    def test_bridge_reports_missing_explicit_root(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(['python3', str(ROOT / 'scripts/ringer_bridge.py'), '--print-root'],
                                    env={**os.environ, 'RINGER_ROOT': tmp},
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Set RINGER_ROOT', result.stderr)

    def test_build_from_canonical_skills(self):
        source = ROOT.parents[2] / '_Core/library/skills/agent-operations'
        if not (source / 'ringer/SKILL.md').is_file():
            self.skipTest('Canonical library not available on this machine')
        before = {name: (source / name / 'SKILL.md').read_bytes()
                  for name in ('ringer', 'cross-review-gate')}
        with tempfile.TemporaryDirectory(prefix='ringer plugin ') as tmp:
            result = subprocess.run(['python3', str(ROOT / 'scripts/install_ringer.py'),
                                     '--source', str(source), '--output', tmp],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            package = Path(tmp) / 'ringer'
            gate = (package / 'skills/cross-review-gate/SKILL.md').read_text()
            self.assertNotIn('codex-companion.mjs', gate)
            self.assertNotIn('/codex:setup', gate)
            self.assertIn('Claude seat provides cross-vendor', gate)
            self.assertIn('Freeze the artifact', gate)
            self.assertIn('sole-finder', gate)
            skill = (package / 'skills/ringer/SKILL.md').read_text()
            self.assertIn('ringer_bridge.py', skill)
            self.assertNotIn('../../../templates/', skill)
            self.assertFalse(any(p.is_symlink() for p in package.rglob('*')))
            self.assertFalse((package / 'config.toml').exists())
            # The bridge runs the existing tool from an unrelated working directory.
            probe = subprocess.run(['python3', str(package / 'scripts/ringer_bridge.py'),
                                    '--no-self-update', '--help'], cwd='/',
                                   capture_output=True, text=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertIn('deterministic parallel AI-agent orchestrator', probe.stdout)
        self.assertEqual(before, {name: (source / name / 'SKILL.md').read_bytes()
                                  for name in before})


if __name__ == '__main__':
    unittest.main()
