import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PMModelPolicyTests(unittest.TestCase):
    def test_source_declares_session_and_review_tiers(self):
        manifest = json.loads((ROOT / 'pm/.claude-plugin/plugin.json').read_text())
        self.assertEqual(manifest['version'], '0.20.0')

        workflow = (ROOT / 'pm/WORKFLOW.md').read_text()
        flat_workflow = ' '.join(workflow.split())
        self.assertIn('`gpt-5.6-sol` in Codex', workflow)
        self.assertIn('`claude-opus-5` in Claude Code', workflow)
        self.assertIn('`gpt-6-astra` and `claude-fable-5` are review seats', workflow)
        self.assertIn('only through Ringer', flat_workflow)
        self.assertIn('account capacity consumed per accepted outcome', workflow)

        orchestrate = (ROOT / 'pm/skills/orchestrate/SKILL.md').read_text()
        flat_orchestrate = ' '.join(orchestrate.split())
        self.assertIn('least costly locally proven model', orchestrate)
        self.assertIn('Astra and Fable are review capacity', flat_orchestrate)

        host = (ROOT / 'pm/skills/session-succession/host.md').read_text()
        flat_host = ' '.join(host.split())
        self.assertIn('ordinary session tier', host)
        self.assertIn('Opus for Claude Code', host)
        self.assertIn('Astra and Fable remain Ringer review seats', flat_host)
        self.assertIn('select `claude-opus-5`', host)

        starter = (ROOT / 'pm/template/CLAUDE.md').read_text()
        flat_starter = ' '.join(starter.split())
        self.assertIn('Sol in Codex and Opus in Claude Code', flat_starter)
        self.assertIn('Astra and Fable through Ringer', flat_starter)

    def test_codex_build_preserves_model_economy_boundary(self):
        with tempfile.TemporaryDirectory(prefix='pm model policy ') as tmp:
            result = subprocess.run(
                ['python3', str(ROOT / 'scripts/build_codex.py'), '--plugin', 'pm',
                 '--output', tmp],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            pm = Path(tmp) / 'pm'
            manifest = json.loads((pm / '.codex-plugin/plugin.json').read_text())
            self.assertTrue(manifest['version'].startswith('0.20.0+codex.'))

            workflow = (pm / 'WORKFLOW.md').read_text()
            flat_workflow = ' '.join(workflow.split())
            self.assertIn('`gpt-5.6-sol` in Codex', workflow)
            self.assertIn('`claude-opus-5` in Claude Code', workflow)
            self.assertIn('`gpt-6-astra` and `claude-fable-5` are review seats', workflow)
            self.assertIn('only through Ringer', flat_workflow)

            host = (pm / 'skills/session-succession/host.md').read_text()
            flat_host = ' '.join(host.split())
            self.assertIn('ordinary session tier', host)
            self.assertIn('Sol for Codex', host)
            self.assertIn('Astra and Fable remain Ringer review seats', flat_host)
            self.assertIn('`model: gpt-5.6-sol`', host)

            grill = (pm / 'skills/fast-grill/SKILL.md').read_text()
            self.assertIn('engine `claude`, model `claude-fable-5`', grill)
            self.assertIn('through Ringer', grill)


if __name__ == '__main__':
    unittest.main()
