"""Verify the actual PM template can be consumed by the shared runtime."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT.parents[2] / '_Core/library/skills/agent-operations/build-swarm/scripts'


class ExecutionAgreementIntegrationTests(unittest.TestCase):
    def test_accepted_template_loads_in_canonical_runtime(self):
        if not (RUNTIME / 'agreement.py').is_file():
            self.skipTest('Canonical build-swarm runtime unavailable')
        template = (ROOT / 'pm/skills/discovery/intent-template.md').read_text()
        self.assertIn('"approved": false', template)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for args in [['init', '-q'], ['config', 'user.name', 'Fixture'],
                         ['config', 'user.email', 'fixture@example.invalid']]:
                subprocess.run(['git', '-C', str(repo), *args], check=True)
            # This is a disposable fixture simulating recorded approval, not an actual opt-in.
            (repo / 'intent.md').write_text(template.replace('"approved": false', '"approved": true'))
            subprocess.run(['git', '-C', str(repo), 'add', 'intent.md'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'Fixture intent'], check=True)
            result = subprocess.run(['python3', '-c',
                'import sys,json;sys.path.insert(0,sys.argv[1]);import agreement;'
                'print(json.dumps(agreement.load(sys.argv[2],"intent.md")))',
                str(RUNTIME), str(repo)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            policy = json.loads(result.stdout)
            self.assertEqual(policy['review']['seats'], ['gpt-6-astra', 'claude-fable-5'])
            self.assertEqual(policy['build']['max_worker_attempts'], 4)


if __name__ == '__main__':
    unittest.main()
