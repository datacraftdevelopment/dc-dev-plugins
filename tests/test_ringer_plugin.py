from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RingerPluginTests(unittest.TestCase):
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
