"""Round-2 residual boundary variants at the acceptance CLI seam.

Horizontal-whitespace runs inside a policy-section label are attempted
headings, never absence — both `## Execution agreement` and
`## Evidence requirements` fail closed on a spacing typo while canonical
headings and ordinary topic titles keep their behavior. Implementer and
evaluator identities are nonempty scalar strings before any independence
comparison, at the top level and in every supplied channel.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pm_evidence_channels as pm


class HeadingWhitespaceVariants(unittest.TestCase):
    def setUp(self):
        self.case = pm.EvidenceChannelCliTests('test_cli_matching_requirements_ship')
        self.case.setUp()

    def legacy_record(self):
        del self.case.record['evidence_requirements']
        for phase in ('local', 'delivery'):
            for check in self.case.record[phase]['checks']:
                del check['channels']

    def test_canonical_headings_still_ship(self):
        result = self.case.run_cli(pm.intent_text())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')

    def test_legacy_intent_without_policy_sections_still_ships(self):
        self.legacy_record()
        result = self.case.run_cli(pm.intent_text(agreement=None, requirements=None))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')

    def test_whitespace_inside_agreement_label_fails_closed(self):
        for spacing in ('  ', '\t', '   ', ' \t ', '\u00a0', '\u2002', '\u3000'):
            with self.subTest(spacing=repr(spacing)):
                self.setUp()
                self.legacy_record()
                text = pm.intent_text(requirements=None).replace(
                    '## Execution agreement', '## Execution' + spacing + 'agreement')
                result = self.case.run_cli(text)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('Execution agreement', result.stdout)

    def test_whitespace_inside_requirements_label_fails_closed(self):
        for spacing in ('  ', '\t', '\u00a0', '\u2002', '\u3000'):
            with self.subTest(spacing=repr(spacing)):
                self.setUp()
                self.legacy_record()
                text = pm.intent_text(agreement=None).replace(
                    '## Evidence requirements', '## Evidence' + spacing + 'requirements')
                result = self.case.run_cli(text)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('Evidence requirements', result.stdout)

    def test_topic_titles_mentioning_the_labels_stay_legacy(self):
        # Headings that merely mention a policy phrase mid-title are not attempts.
        self.legacy_record()
        text = (pm.intent_text(agreement=None, requirements=None)
                + '\n## Notes on the Execution agreement\n\nProse.\n'
                + '\n## Why we skipped Evidence requirements\n\nProse.\n')
        result = self.case.run_cli(text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')


class IdentityScalarVariants(unittest.TestCase):
    NONSCALAR = (['worker-1'], {'id': 'worker-1'}, True, 123, '   ')

    def setUp(self):
        self.case = pm.EvidenceChannelCliTests('test_cli_matching_requirements_ship')
        self.case.setUp()

    def run_blocked(self):
        result = self.case.run_cli(pm.intent_text())
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_nonscalar_channel_evaluator_blocks(self):
        for value in self.NONSCALAR:
            with self.subTest(value=value):
                self.setUp()
                for phase in ('local', 'delivery'):
                    self.case.record[phase]['checks'][1]['channels']['ui']['evaluator'] = value
                self.run_blocked()

    def test_nonscalar_check_evaluator_blocks(self):
        for value in self.NONSCALAR:
            with self.subTest(value=value):
                self.setUp()
                for phase in ('local', 'delivery'):
                    self.case.record[phase]['checks'][0]['evaluator'] = value
                self.run_blocked()

    def test_nonscalar_implementer_blocks(self):
        for value in self.NONSCALAR:
            with self.subTest(value=value):
                self.setUp()
                self.case.record['implementer'] = value
                self.run_blocked()

    def test_distinct_scalar_identities_still_ship(self):
        for phase in ('local', 'delivery'):
            self.case.record[phase]['checks'][1]['channels']['ui']['evaluator'] = 'ui-verifier-2'
        result = self.case.run_cli(pm.intent_text())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'shipped')


if __name__ == '__main__':
    unittest.main(verbosity=2)
