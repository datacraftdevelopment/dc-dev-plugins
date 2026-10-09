import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PMModelPolicyTests(unittest.TestCase):
    def test_source_declares_session_and_review_tiers(self):
        manifest = json.loads((ROOT / 'pm/.claude-plugin/plugin.json').read_text())
        self.assertEqual(manifest['version'], '0.26.8')

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
        self.assertIn('docs/agents/worker-env.md', starter)

    def test_source_declares_orchestrated_run_rules(self):
        workflow = ' '.join((ROOT / 'pm/WORKFLOW.md').read_text().split())
        self.assertIn('Lead seat of an orchestrated run', workflow)
        self.assertIn('fresh session from a written brief', workflow)
        self.assertIn('manager-only', workflow)
        self.assertIn('never implementation workers', workflow)
        self.assertIn('integration branch', workflow)

        orchestrate = ' '.join(
            (ROOT / 'pm/skills/orchestrate/SKILL.md').read_text().split())
        for rule in (
            'fresh session from a written brief',
            '150K',
            'acceptance tests before dispatch',
            'docs/agents/worker-env.md',
            'integration branch',
            'closed only by Joe',
            'never silently dropped',
            'One wave per Ringer run',
            'CPU load',
            'regenerates generated artifacts',
            'manager-only',
        ):
            self.assertIn(rule, orchestrate)

    def test_default_loop_is_one_session_with_an_offered_successor(self):
        flat = lambda path: ' '.join((ROOT / path).read_text().split())
        workflow = flat('pm/WORKFLOW.md')
        self.assertIn('Default loop', workflow)
        self.assertIn('Orchestration is opt-in', workflow)
        self.assertIn('Sibling sessions', workflow)
        self.assertIn('Nobody watches them', workflow)
        self.assertIn('Do the work in this session', flat('pm/skills/whats-next/SKILL.md'))
        away = flat('pm/skills/stepping-away/SKILL.md')
        self.assertIn('offer to open a fresh session', away)
        self.assertIn('never running', away)
        starter = flat('pm/template/CLAUDE.md')
        self.assertIn('Do not orchestrate by default', starter)
        self.assertIn('sibling sessions', starter)

        sibling = (ROOT / 'pm/skills/sibling-sessions/SKILL.md').read_text()
        header = sibling.split('---')[1]
        self.assertIn('name: sibling-sessions', header)
        self.assertIn('implement sibling sessions if appropriate', header)
        flat_sibling = ' '.join(sibling.split())
        for rule in ('nobody watches them', 'Disjoint files',
                     'At most one database writer', 'Three siblings at once is the ceiling',
                     'created and pending', 'Merge on the user\'s word'):
            self.assertIn(rule, flat_sibling)
        self.assertIn('sibling-sessions', flat('pm/skills/whats-next/SKILL.md'))
        self.assertIn('sibling-sessions', flat('pm/skills/stepping-away/SKILL.md'))

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
            self.assertTrue(manifest['version'].startswith('0.26.8+codex.'))

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

            flat_workflow_all = flat_workflow
            self.assertIn('Lead seat of an orchestrated run', flat_workflow_all)
            self.assertIn('manager-only', flat_workflow_all)

            orchestrate = ' '.join(
                (pm / 'skills/orchestrate/SKILL.md').read_text().split())
            self.assertIn('fresh session from a written brief', orchestrate)
            self.assertIn('docs/agents/worker-env.md', orchestrate)
            self.assertIn('closed only by Joe', orchestrate)

            self.assertTrue((pm / 'skills/sibling-sessions/SKILL.md').is_file())

            grill = (pm / 'skills/fast-grill/SKILL.md').read_text()
            self.assertIn('engine `claude`, model `claude-fable-5`', grill)
            self.assertIn('through Ringer', grill)


if __name__ == '__main__':
    unittest.main()
