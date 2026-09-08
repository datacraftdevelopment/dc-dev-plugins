import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'pm/scripts/acceptance.py'
        self.assertTrue(path.exists(), 'acceptance record validator has not been implemented')
        spec = importlib.util.spec_from_file_location('acceptance', path)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.record = {'intent':'docs/intent/test.md', 'criteria':{'A1':'Run CLI → prints hello'},
                       'candidate':'abc123', 'implementer':'worker-1',
                       'local':{'revision':'abc123','environment':'scratch', 'checks':[
                           {'id':'A1', 'status':'pass', 'evidence':'stdout: hello', 'evaluator':'reviewer-2', 'at':'2026-09-08T01:00:00Z'}]}}

    def test_local_ready_and_delivery_revision_must_match(self):
        self.assertEqual(self.module.verdict(self.record), 'ready-for-release')
        self.record['delivery'] = {**self.record['local'], 'revision':'wrong', 'environment':'production', 'applied_by':'Joe'}
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_manual_missing_and_partial_checks_are_not_shipped(self):
        self.record['local']['checks'][0]['status']='not-run'
        self.assertEqual(self.module.verdict(self.record), 'blocked')
        self.record['local']['checks']=[]
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_independent_evaluator_and_evidence_required(self):
        self.record['local']['checks'][0]['evaluator']='worker-1'
        self.assertEqual(self.module.verdict(self.record), 'blocked')
        self.record['local']['checks'][0]['evaluator']='reviewer-2'
        self.record['local']['checks'][0]['evidence']=''
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_nondeployed_delivery_and_explicit_exception(self):
        self.record['delivery'] = {**self.record['local'], 'kind':'artifact', 'environment':'delivered CLI archive', 'applied_by':'Joe'}
        self.assertEqual(self.module.verdict(self.record), 'shipped')
        self.record['delivery']['checks']=[dict(self.record['local']['checks'][0],status='fail')]
        self.assertEqual(self.module.verdict(self.record), 'blocked')
        self.record['exceptions']=[{'id':'A1','phase':'delivery','approved_by':'Joe','reason':'Accept this documented limitation','at':'2026-09-08'}]
        self.assertEqual(self.module.verdict(self.record), 'released-with-exceptions')

    def test_cli_does_not_accept_omitted_intent_criterion(self):
        with tempfile.TemporaryDirectory() as tmp:
            intent = Path(tmp) / 'intent.md'
            intent.write_text('# Intent\nStatus: accepted\n\n## Acceptance\n- [ ] A1: Run CLI → prints hello\n- [ ] A2: Run bye → prints goodbye\n\n## Constraints\nNone\n')
            self.record['intent_sha256'] = hashlib.sha256(intent.read_bytes()).hexdigest()
            record = Path(tmp) / 'record.json'
            record.write_text(json.dumps(self.record))
            p = subprocess.run(['python3', str(ROOT / 'pm/scripts/acceptance.py'), '--record', str(record),
                                '--intent', str(intent)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 2, p.stdout)
            self.assertIn('criteria', p.stdout)
