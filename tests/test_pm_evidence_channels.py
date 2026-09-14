"""Required evidence channels at the acceptance CLI seam (dc-autonomy-v1).

The validator proves completeness and identity consistency of channel
evidence — never genuine media content or actual human approval.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

AGREEMENT = ('{"policy": "dc-autonomy-v1", "approved": true, "scope": "hello CLI plus invoice posting", '
             '"actions": ["local-edit", "local-test"], "technical_choices": [], '
             '"frontend_checkpoints": ["prototype", "final-demo"], "test_targets": ["tests"], '
             '"review": {"seats": ["gpt-6-astra", "claude-fable-5"], "max_rounds": 3, "independent_confirmation": true}, '
             '"build": {"max_worker_attempts": 4, "recovery_cycles": 1, "max_tasks": 3}}')

REQUIREMENTS = '{"A1": ["automated"], "A2": ["ui", "state"]}'


def intent_text(agreement=AGREEMENT, requirements=REQUIREMENTS):
    text = ('# Intent: hello CLI\nStatus: accepted\n\n## Acceptance\n'
            '- [ ] A1: Run CLI → prints hello\n'
            '- [ ] A2: Post the invoice → status shows Posted and the row persists\n\n')
    if agreement is not None:
        text += '## Execution agreement\n\n```json\n' + agreement + '\n```\n\n'
    if requirements is not None:
        text += '## Evidence requirements\n\n```json\n' + requirements + '\n```\n\n'
    return text + '## Constraints\nNone\n'


def channel(evaluator, status='pass', revision='abc123'):
    return {'status': status, 'evaluator': evaluator, 'evidence': 'captured artifact',
            'at': '2026-09-14T01:00:00Z', 'revision': revision}


class EvidenceChannelVerdictTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'pm/scripts/acceptance.py'
        spec = importlib.util.spec_from_file_location('acceptance', path)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.record = {
            'intent': 'docs/intent/test.md',
            'criteria': {'A1': 'Run CLI → prints hello',
                         'A2': 'Post the invoice → status shows Posted and the row persists'},
            'candidate': 'abc123', 'implementer': 'worker-1',
            'evidence_requirements': json.loads(REQUIREMENTS),
            'local': {'revision': 'abc123', 'environment': 'scratch', 'checks': [
                {'id': 'A1', 'status': 'pass', 'evidence': 'stdout: hello', 'evaluator': 'reviewer-2',
                 'at': '2026-09-14T01:00:00Z', 'channels': {'automated': channel('reviewer-2')}},
                {'id': 'A2', 'status': 'pass', 'evidence': 'receipt + rows', 'evaluator': 'reviewer-2',
                 'at': '2026-09-14T01:00:00Z',
                 'channels': {'ui': channel('ui-verifier'), 'state': channel('reviewer-2')}}]},
        }

    def with_delivery(self):
        self.record['delivery'] = copy.deepcopy(self.record['local'])
        self.record['delivery'].update(environment='production', applied_by='Joe')

    def a2(self, phase='local'):
        return self.record[phase]['checks'][1]

    def test_all_required_independent_channels_yield_readiness(self):
        self.assertEqual(self.module.verdict(self.record), 'ready-for-release')
        self.with_delivery()
        self.assertEqual(self.module.verdict(self.record), 'shipped')

    def test_code_pass_with_missing_ui_channel_blocks(self):
        del self.a2()['channels']['ui']
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_code_pass_with_failed_ui_channel_blocks(self):
        self.a2()['channels']['ui']['status'] = 'fail'
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_pixels_pass_state_failure_blocks(self):
        self.a2()['channels']['state']['status'] = 'fail'
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_self_evaluation_on_a_channel_blocks_even_with_exception(self):
        self.a2()['channels']['state']['evaluator'] = 'worker-1'
        self.assertEqual(self.module.verdict(self.record), 'blocked')
        self.record['exceptions'] = [{'id': 'A2', 'phase': 'local', 'channel': 'state',
                                      'approved_by': 'Joe', 'reason': 'accept', 'at': '2026-09-14'}]
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_wrong_channel_revision_blocks(self):
        self.a2()['channels']['ui']['revision'] = 'older-build'
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_scoped_exception_qualifies_but_never_ships_unqualified(self):
        self.with_delivery()
        self.a2('delivery')['channels']['ui']['status'] = 'not-run'
        self.assertEqual(self.module.verdict(self.record), 'blocked')
        # A criterion-level exception is not scoped to the channel and must not cover it.
        self.record['exceptions'] = [{'id': 'A2', 'phase': 'delivery',
                                      'approved_by': 'Joe', 'reason': 'no runner on prod host', 'at': '2026-09-14'}]
        self.assertEqual(self.module.verdict(self.record), 'blocked')
        self.record['exceptions'][0]['channel'] = 'ui'
        self.assertEqual(self.module.verdict(self.record), 'released-with-exceptions')

    def test_missing_required_channel_with_scoped_exception_is_qualified(self):
        self.with_delivery()
        del self.a2('delivery')['channels']['ui']
        self.record['exceptions'] = [{'id': 'A2', 'phase': 'delivery', 'channel': 'ui',
                                      'approved_by': 'Joe', 'reason': 'no GUI on prod host', 'at': '2026-09-14'}]
        self.assertEqual(self.module.verdict(self.record), 'released-with-exceptions')

    def test_channel_entry_missing_fields_blocks(self):
        for field in ('status', 'evaluator', 'evidence', 'at', 'revision'):
            record = copy.deepcopy(self.record)
            del record['local']['checks'][1]['channels']['ui'][field]
            self.assertEqual(self.module.verdict(record), 'blocked', field)

    def test_malformed_requirements_fail_closed(self):
        for bad in ({'A2': ['pixels']},          # unknown channel name
                    {'A2': ['ui', 'state']},     # missing criterion A1
                    {'A2': []},                  # empty channel list
                    {'A9': ['ui']},              # id not in criteria
                    {'A2': 'ui'},                # wrong type
                    {}):                         # empty mapping
            record = copy.deepcopy(self.record)
            record['evidence_requirements'] = bad
            self.assertEqual(self.module.verdict(record), 'blocked', repr(bad))

    def test_unknown_supplied_channel_name_blocks(self):
        self.a2()['channels']['narrative'] = channel('ui-verifier')
        self.assertEqual(self.module.verdict(self.record), 'blocked')

    def test_legacy_record_without_requirements_keeps_current_behavior(self):
        del self.record['evidence_requirements']
        for check in self.record['local']['checks']:
            del check['channels']
        self.assertEqual(self.module.verdict(self.record), 'ready-for-release')
        self.with_delivery()
        self.assertEqual(self.module.verdict(self.record), 'shipped')


class EvidenceChannelCliTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            'acceptance', ROOT / 'pm/scripts/acceptance.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        base = EvidenceChannelVerdictTests('setUp')
        base.setUp()
        self.record = base.record
        self.record['delivery'] = copy.deepcopy(self.record['local'])
        self.record['delivery'].update(environment='production', applied_by='Joe')

    def run_cli(self, intent, record_json=None):
        with tempfile.TemporaryDirectory() as tmp:
            intent_path = Path(tmp) / 'intent.md'
            intent_path.write_text(intent)
            self.record['intent_sha256'] = hashlib.sha256(intent_path.read_bytes()).hexdigest()
            record_path = Path(tmp) / 'record.json'
            if record_json is None:
                record_path.write_text(json.dumps(self.record))
            else:
                # raw JSON is written verbatim so duplicate keys survive; the
                # caller marks the digest slot with the literal token DIGEST
                record_path.write_text(record_json.replace('DIGEST', self.record['intent_sha256']))
            return subprocess.run([sys.executable, str(ROOT / 'pm/scripts/acceptance.py'),
                                   '--record', str(record_path), '--intent', str(intent_path)],
                                  capture_output=True, text=True)

    def test_cli_matching_requirements_ship(self):
        result = self.run_cli(intent_text())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')

    def test_cli_blocks_record_that_omits_ui_requirements(self):
        # The record author must echo the accepted intent's mapping exactly —
        # silently narrowing A2 to state-only is an identity mismatch.
        self.record['evidence_requirements'] = {'A1': ['automated'], 'A2': ['state']}
        result = self.run_cli(intent_text())
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('evidence', result.stdout)
        del self.record['evidence_requirements']
        result = self.run_cli(intent_text())
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_cli_blocks_duplicate_keys_in_requirements_block(self):
        result = self.run_cli(intent_text(requirements='{"A1": ["automated"], "A1": ["human"], "A2": ["ui", "state"]}'))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('duplicate', result.stdout)

    def test_cli_blocks_adopted_autonomy_intent_without_requirements(self):
        result = self.run_cli(intent_text(requirements=None))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('Evidence requirements', result.stdout)

    def test_cli_blocks_malformed_agreement(self):
        result = self.run_cli(intent_text(agreement='{"policy": "dc-autonomy-v2", "approved": true}'))
        self.assertEqual(result.returncode, 2, result.stdout)
        result = self.run_cli(intent_text(agreement='{"policy": "dc-autonomy-v1", "approved": "yes"}'))
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_cli_unapproved_template_agreement_needs_no_requirements(self):
        self.record['evidence_requirements'] = None
        del self.record['evidence_requirements']
        for phase in ('local', 'delivery'):
            for check in self.record[phase]['checks']:
                del check['channels']
        result = self.run_cli(intent_text(agreement=AGREEMENT.replace('"approved": true', '"approved": false'),
                                          requirements=None))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_blocks_duplicate_keys_in_record(self):
        payload = dict(self.record)
        payload['intent_sha256'] = 'DIGEST'
        raw = json.dumps(payload)[:-1] + ', "criteria": {"A1": "x"}}'
        result = self.run_cli(intent_text(), record_json=raw)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('duplicate', result.stdout)

    def test_cli_legacy_intent_without_blocks_retains_behavior(self):
        del self.record['evidence_requirements']
        for phase in ('local', 'delivery'):
            for check in self.record[phase]['checks']:
                del check['channels']
        result = self.run_cli(intent_text(agreement=None, requirements=None))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')


if __name__ == '__main__':
    unittest.main()
