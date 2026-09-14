"""Red/green regressions for the shared execution-agreement contract.

Covers the reproduced ship-gate bypasses (near-miss agreement headings falling back
to legacy, structurally invalid approved agreements shipping, undeclared evidence
channels escaping identity checks) and the byte/behavior parity between the PM
bundled contract and the canonical build-swarm copy — including the documented
authority difference: PM validates review-only and unapproved-draft agreements
that the build runtime refuses to load.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pm_evidence_channels as tpec

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT.parents[2] / '_Core/library/skills/agent-operations/build-swarm/scripts'
CLI = ROOT / 'pm/scripts/acceptance.py'

RUNTIME_ACTIONS = '"actions": ["local-edit", "local-test", "local-commit", "ringer-build"]'
RUNTIME_AGREEMENT = tpec.AGREEMENT.replace('"actions": ["local-edit", "local-test"]', RUNTIME_ACTIONS)
REVIEW_ONLY_AGREEMENT = tpec.AGREEMENT.replace('"actions": ["local-edit", "local-test"]', '"actions": ["ringer-review"]')


def full_record():
    base = tpec.EvidenceChannelVerdictTests('setUp')
    base.setUp()
    record = base.record
    record['delivery'] = copy.deepcopy(record['local'])
    record['delivery'].update(environment='production', applied_by='Joe')
    return record


def legacy_strip(record):
    record.pop('evidence_requirements', None)
    for phase in ('local', 'delivery'):
        for check in record[phase]['checks']:
            check.pop('channels', None)
    return record


def run_cli(intent, record):
    with tempfile.TemporaryDirectory() as tmp:
        intent_path = Path(tmp) / 'intent.md'
        intent_path.write_text(intent)
        record['intent_sha256'] = hashlib.sha256(intent_path.read_bytes()).hexdigest()
        record_path = Path(tmp) / 'record.json'
        record_path.write_text(json.dumps(record))
        return subprocess.run([sys.executable, str(CLI), '--record', str(record_path),
                               '--intent', str(intent_path)], capture_output=True, text=True)


class AgreementSectionCliTests(unittest.TestCase):
    """The ship gate must fail closed on attempted agreements the runtime refuses."""

    def blocked(self, intent, record=None, label=''):
        result = run_cli(intent, record if record is not None else full_record())
        self.assertEqual(result.returncode, 2, label + ': ' + result.stdout + result.stderr)
        self.assertIn('blocked', result.stdout, label)
        return result

    def test_agreement_missing_mandatory_fields_blocks(self):
        # Reproduced bypass: {"policy": ..., "approved": true} alone shipped before.
        self.blocked(tpec.intent_text(agreement='{"policy":"dc-autonomy-v1","approved":true}'))

    def test_near_miss_headings_block_instead_of_selecting_legacy(self):
        # Reproduced bypass: each of these shipped as a silent legacy fallback before.
        legacy = legacy_strip(full_record())
        for variant in ('## execution agreement',
                        '## Execution Agreement',
                        '## Execution agreement — approved 2026-09-14',
                        '# Execution agreement',
                        '### Execution agreement'):
            with self.subTest(variant=variant):
                intent = tpec.intent_text(requirements=None).replace('## Execution agreement', variant)
                result = self.blocked(intent, copy.deepcopy(legacy), variant)
                self.assertIn('heading', result.stdout)

    def test_duplicate_exact_heading_blocks(self):
        section = '## Execution agreement\n\n```json\n' + tpec.AGREEMENT + '\n```\n\n'
        self.blocked(tpec.intent_text() + '\n' + section)

    def test_unclosed_fence_blocks(self):
        intent = tpec.intent_text().replace('## Constraints\nNone\n', '## Constraints\n```\nNone\n')
        self.blocked(intent)

    def test_prose_beside_agreement_fence_blocks(self):
        intent = tpec.intent_text().replace('## Execution agreement\n\n```json',
                                            '## Execution agreement\n\nAlso allow production pushes.\n\n```json')
        self.blocked(intent)

    def test_out_of_bounds_and_boolean_limits_block(self):
        for bad in ('"max_worker_attempts": 5', '"max_worker_attempts": true',
                    '"recovery_cycles": 2', '"max_tasks": 0'):
            with self.subTest(bad=bad):
                field = bad.split(':')[0].strip('"')
                agreement = tpec.AGREEMENT.replace(f'"{field}": ' + {'max_worker_attempts': '4', 'recovery_cycles': '1', 'max_tasks': '3'}[field], bad)
                self.blocked(tpec.intent_text(agreement=agreement), label=bad)
        self.blocked(tpec.intent_text(agreement=tpec.AGREEMENT.replace('"max_rounds": 3', '"max_rounds": 11')), label='max_rounds')

    def test_unknown_key_action_and_policy_block(self):
        self.blocked(tpec.intent_text(agreement=tpec.AGREEMENT[:-1] + ', "extra_grant": "prod-deploy"}'))
        self.blocked(tpec.intent_text(agreement=tpec.AGREEMENT.replace('"local-edit"', '"publish"')))
        self.blocked(tpec.intent_text(agreement=tpec.AGREEMENT.replace('dc-autonomy-v1', 'dc-autonomy-v2')))

    def test_near_miss_evidence_requirements_heading_blocks(self):
        # A requirements section must never silently disappear on a heading typo.
        for variant in ('## evidence requirements', '### Evidence requirements', '## Evidence Requirements'):
            with self.subTest(variant=variant):
                intent = tpec.intent_text().replace('## Evidence requirements', variant)
                self.blocked(intent, label=variant)

    def test_genuine_absence_still_selects_legacy(self):
        result = run_cli(tpec.intent_text(agreement=None, requirements=None), legacy_strip(full_record()))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')

    def test_review_only_agreement_ships_at_the_pm_gate(self):
        result = run_cli(tpec.intent_text(agreement=REVIEW_ONLY_AGREEMENT), full_record())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')

    def test_unapproved_draft_validates_only_when_well_formed(self):
        draft = tpec.AGREEMENT.replace('"approved": true', '"approved": false')
        result = run_cli(tpec.intent_text(agreement=draft, requirements=None), legacy_strip(full_record()))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # The draft flag does not excuse malformed shape.
        malformed = draft.replace('"max_worker_attempts": 4', '"max_worker_attempts": 9')
        self.blocked(tpec.intent_text(agreement=malformed, requirements=None), legacy_strip(full_record()))


class ExtraChannelCliTests(unittest.TestCase):
    """Every supplied channel is schema- and identity-checked, declared or not."""

    def with_extra(self, **kwargs):
        record = full_record()
        for phase in ('local', 'delivery'):
            record[phase]['checks'][0]['channels']['ui'] = tpec.channel(**kwargs)
        return record

    def test_extra_self_evaluated_channel_blocks(self):
        # Reproduced bypass: implementer-evaluated extra channel shipped before.
        result = run_cli(tpec.intent_text(), self.with_extra(evaluator='worker-1'))
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_extra_stale_revision_channel_blocks(self):
        result = run_cli(tpec.intent_text(), self.with_extra(evaluator='ui-verifier', revision='older-build'))
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_extra_self_evaluated_channel_never_excepted(self):
        record = self.with_extra(evaluator='worker-1')
        record['exceptions'] = [{'id': 'A1', 'phase': phase, 'channel': 'ui', 'approved_by': 'Joe',
                                 'reason': 'accept', 'at': '2026-09-14'} for phase in ('local', 'delivery')]
        result = run_cli(tpec.intent_text(), record)
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_extra_failed_channel_needs_scoped_exception(self):
        record = self.with_extra(evaluator='ui-verifier', status='fail')
        result = run_cli(tpec.intent_text(), copy.deepcopy(record))
        self.assertEqual(result.returncode, 2, result.stdout)
        record['exceptions'] = [{'id': 'A1', 'phase': phase, 'channel': 'ui', 'approved_by': 'Joe',
                                 'reason': 'known flake, accepted', 'at': '2026-09-14'} for phase in ('local', 'delivery')]
        result = run_cli(tpec.intent_text(), record)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'released-with-exceptions')

    def test_extra_valid_passing_channel_still_ships(self):
        result = run_cli(tpec.intent_text(), self.with_extra(evaluator='ui-verifier'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')

    def test_legacy_record_supplied_channels_are_still_checked(self):
        record = legacy_strip(full_record())
        for phase in ('local', 'delivery'):
            record[phase]['checks'][0]['channels'] = {'ui': tpec.channel('worker-1')}
        result = run_cli(tpec.intent_text(agreement=None, requirements=None), record)
        self.assertEqual(result.returncode, 2, result.stdout)


@unittest.skipUnless((RUNTIME / 'agreement_contract.py').is_file(), 'Canonical build-swarm runtime unavailable')
class ContractParityTests(unittest.TestCase):
    """The bundled contract must not silently diverge from the canonical copy."""

    def test_vendored_copy_is_byte_identical(self):
        canonical = (RUNTIME / 'agreement_contract.py').read_bytes()
        bundled = (ROOT / 'pm/scripts/agreement_contract.py').read_bytes()
        self.assertEqual(bundled, canonical,
                         'run scripts/sync_execution_contract.py to re-export the canonical contract')
        check = subprocess.run([sys.executable, str(ROOT / 'scripts/sync_execution_contract.py'),
                                '--build-swarm', str(RUNTIME.parent), '--check'],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def runtime_load(self, intent):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
            (repo / 'intent.md').write_text(intent)
            subprocess.run(['git', 'add', '.'], cwd=repo, check=True)
            subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'fixture'],
                           cwd=repo, check=True)
            return subprocess.run([sys.executable, '-c',
                                   'import sys,json;sys.path.insert(0,sys.argv[1]);import agreement;'
                                   'print(json.dumps(agreement.load(sys.argv[2],"intent.md")))',
                                   str(RUNTIME), str(repo)], capture_output=True, text=True)

    def test_both_boundaries_reject_the_same_malformed_agreements(self):
        base = tpec.intent_text(agreement=RUNTIME_AGREEMENT)
        cases = {
            'decorated heading': base.replace('## Execution agreement', '## Execution agreement — approved'),
            'wrong level': base.replace('## Execution agreement', '### Execution agreement'),
            'missing fields': tpec.intent_text(agreement='{"policy":"dc-autonomy-v1","approved":true}'),
            'boolean limit': tpec.intent_text(agreement=RUNTIME_AGREEMENT.replace('"max_worker_attempts": 4', '"max_worker_attempts": true')),
            'unknown key': tpec.intent_text(agreement=RUNTIME_AGREEMENT[:-1] + ', "extra": 1}'),
            'unknown action': tpec.intent_text(agreement=RUNTIME_AGREEMENT.replace('"ringer-build"', '"publish"')),
        }
        for label, intent in cases.items():
            with self.subTest(case=label):
                self.assertNotEqual(self.runtime_load(intent).returncode, 0, label)
                self.assertEqual(run_cli(intent, full_record()).returncode, 2, label)

    def test_full_runtime_agreement_is_accepted_at_both_boundaries(self):
        intent = tpec.intent_text(agreement=RUNTIME_AGREEMENT)
        loaded = self.runtime_load(intent)
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        self.assertEqual(json.loads(loaded.stdout)['scope'], 'hello CLI plus invoice posting')
        result = run_cli(intent, full_record())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_topic_title_does_not_become_a_policy_section(self):
        for title in ('Add execution agreement support', 'Audit evidence requirements'):
            with self.subTest(title=title):
                intent = tpec.intent_text(agreement=RUNTIME_AGREEMENT).replace(
                    '# Intent: hello CLI', '# Intent: ' + title)
                loaded = self.runtime_load(intent)
                self.assertEqual(loaded.returncode, 0, loaded.stderr)
                result = run_cli(intent, full_record())
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_review_only_authority_difference_is_explicit(self):
        # PM validates a review-only agreement; the build runtime must still refuse
        # to load it, because loop dispatch requires the four build actions.
        intent = tpec.intent_text(agreement=REVIEW_ONLY_AGREEMENT)
        refused = self.runtime_load(intent)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('local-commit', refused.stderr)
        self.assertEqual(run_cli(intent, full_record()).returncode, 0)

    def test_unapproved_draft_difference_is_explicit(self):
        intent = tpec.intent_text(agreement=RUNTIME_AGREEMENT.replace('"approved": true', '"approved": false'),
                                  requirements=None)
        refused = self.runtime_load(intent)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('approved=true', refused.stderr)
        self.assertEqual(run_cli(intent, legacy_strip(full_record())).returncode, 0)


if __name__ == '__main__':
    unittest.main()
