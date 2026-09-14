import concurrent.futures
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'pm/scripts/succession.py'
SESSION = ROOT / 'pm/scripts/session.py'


class SuccessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / '.gitignore').write_text((ROOT / 'pm/template/.gitignore').read_text())
        self.policy = {'policy': 'dc-succession-beta-v1', 'approved': True,
                       'scope': 'Fixture tickets', 'max_sessions': 3,
                       'allow_create_successor': True,
                       'authorization_ref': 'intent.md'}
        (self.repo / 'policy.json').write_text(json.dumps(self.policy))
        (self.repo / 'intent.md').write_text('User authorized this fixture scope.\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.current = self.open_session()

    def git(self, *args):
        p = subprocess.run(['git', '-C', str(self.repo), *args], text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def cli(self, *args, ok=True):
        p = subprocess.run(['python3', str(SCRIPT), '--root', str(self.repo), *args],
                           text=True, capture_output=True)
        if not ok:
            self.assertNotEqual(p.returncode, 0, p.stdout)
            return p.stderr
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def open_session(self):
        p = subprocess.run(['python3', str(SESSION), '--root', str(self.repo), 'open',
                            '--name', 'joe', '--intent', 'Fixture work.'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def close_session(self, session):
        p = subprocess.run(['python3', str(SESSION), '--root', str(self.repo), 'close',
                            '--session', session['path'], '--id', session['id'],
                            '--entry', 'Verified fixture; next ticket is ready.'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def start(self):
        state = self.cli('start', '--policy-file', 'policy.json', '--host', 'claude',
                         '--actor', 'host-1', '--session', self.current['path'], '--id', self.current['id'])
        self.chain = state['chain_id']
        self.runtime = Path(state['state_path']).parent
        return state

    def action(self, command, *args, **kwargs):
        return self.cli(command, '--chain', self.chain, *args, **kwargs)

    def prepare(self, actor='host-1', ticket='T2'):
        self.close_session(self.current)
        self.git('add', self.current['path'])
        self.git('commit', '-qm', 'Verified session checkpoint')
        brief = {'ticket': ticket, 'revision': self.git('rev-parse', 'HEAD'),
                 'summary': 'Previous ticket verified.', 'decisions': ['Keep scope narrow.'],
                 'verification': ['intent.md'], 'blockers': [], 'next_step': 'Read the ticket and build it.'}
        (self.runtime / 'brief.json').write_text(json.dumps(brief))
        return self.action('prepare', '--actor', actor, '--brief-file', str(self.runtime / 'brief.json'))

    def acknowledge(self, attempt, actor='host-2'):
        successor = self.open_session()
        state = self.action('acknowledge', '--attempt', attempt, '--actor', actor,
                            '--session', successor['path'], '--id', successor['id'])
        return successor, state

    def retire(self, actor='host-1'):
        (self.runtime / 'resources.md').write_text('No owned servers or workers remain. Verified by fixture.')
        return self.action('retire', '--actor', actor, '--evidence-file', str(self.runtime / 'resources.md'))

    def test_opt_in_and_one_chain_per_repository(self):
        self.policy['approved'] = False
        (self.repo / 'policy.json').write_text(json.dumps(self.policy))
        self.assertIn('approved', self.cli('start', '--policy-file', 'policy.json', '--host', 'claude',
                      '--actor', 'host-1', '--session', self.current['path'], '--id', self.current['id'], ok=False))
        self.policy['approved'] = True
        (self.repo / 'policy.json').write_text(json.dumps(self.policy))
        first = self.start()
        self.assertEqual(self.start()['chain_id'], first['chain_id'])
        other = self.open_session()
        self.cli('start', '--policy-file', 'policy.json', '--host', 'claude', '--actor', 'other',
                 '--session', other['path'], '--id', other['id'], ok=False)

    def test_concurrent_launch_only_one_dispatch_and_retry_does_not_spawn(self):
        self.start(); self.prepare()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.action('launch', '--actor', 'host-1'), range(4)))
        self.assertEqual(sum(r['dispatch_allowed'] for r in results), 1)
        self.assertEqual(len({r['handoff']['attempt'] for r in results}), 1)
        self.assertEqual(self.action('status')['phase'], 'launching')
        self.assertFalse(self.action('launch', '--actor', 'host-1')['dispatch_allowed'])

    def test_three_sessions_and_recovery_when_create_receipt_was_lost(self):
        self.start()
        for previous, following, ticket in [('host-1', 'host-2', 'T2'), ('host-2', 'host-3', 'T3')]:
            self.prepare(previous, ticket)
            launched = self.action('launch', '--actor', previous)
            attempt = launched['handoff']['attempt']
            # Simulate parent dying after host creation, before recording its receipt.
            successor, ack = self.acknowledge(attempt, following)
            self.assertEqual(ack['phase'], 'acknowledged')
            self.action('begin', '--actor', following, ok=False)
            self.retire(previous)
            self.assertEqual(self.retire(previous)['phase'], 'retired')
            begun = self.action('begin', '--actor', following)
            self.assertEqual(begun['current']['id'], successor['id'])
            self.assertEqual(self.action('begin', '--actor', following)['phase'], 'active')
            self.current = successor
        self.close_session(self.current)
        self.action('prepare', '--actor', 'host-3', '--brief-file', str(self.runtime / 'brief.json'), ok=False)
        stopped = self.action('stop', '--actor', 'host-3', '--reason', 'Beta session budget reached.')
        self.assertEqual(len(stopped['history']), 2)
        self.assertEqual(stopped['sessions_started'], 3)

    def test_created_is_not_running_and_wrong_successor_is_rejected(self):
        self.start(); self.prepare()
        attempt = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        self.action('created', '--actor', 'host-1', '--attempt', attempt, '--successor', 'host-2')
        self.assertEqual(self.action('status')['phase'], 'created')
        self.action('retire', '--actor', 'host-1', '--evidence-file', 'intent.md', ok=False)
        other = self.open_session()
        self.action('acknowledge', '--actor', 'wrong', '--attempt', attempt,
                    '--session', other['path'], '--id', other['id'], ok=False)
        self.action('acknowledge', '--actor', 'host-2', '--attempt', 'wrong',
                    '--session', other['path'], '--id', other['id'], ok=False)
        (self.repo / other['path']).unlink()
        successor, _ = self.acknowledge(attempt)
        self.action('created', '--actor', 'host-1', '--attempt', attempt, '--successor', 'host-2')
        self.assertEqual(self.action('status')['handoff']['successor']['id'], successor['id'])

    def test_pending_launch_requires_explicit_absence_evidence_before_retry(self):
        self.start(); self.prepare()
        first = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        self.action('stop', '--actor', 'host-1', '--reason', 'timeout', ok=False)
        (self.runtime / 'absence.md').write_text('Fixture host confirms no successor was created.')
        self.action('not-created', '--actor', 'host-1', '--attempt', first,
                    '--evidence-file', str(self.runtime / 'absence.md'))
        second = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        self.assertNotEqual(first, second)
        self.action('created', '--actor', 'host-1', '--attempt', first, '--successor', 'late', ok=False)

    def test_authorization_and_revision_changes_block_startup(self):
        self.start(); self.prepare()
        (self.repo / 'intent.md').write_text('Authorization changed.')
        self.action('launch', '--actor', 'host-1', ok=False)
        (self.repo / 'intent.md').write_text('User authorized this fixture scope.\n')
        attempt = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        self.git('commit', '--allow-empty', '-qm', 'new revision')
        successor = self.open_session()
        self.action('acknowledge', '--actor', 'host-2', '--attempt', attempt,
                    '--session', successor['path'], '--id', successor['id'], ok=False)

    def test_closed_binding_clean_tree_and_compact_brief_required(self):
        self.start()
        (self.runtime / 'brief.json').write_text('{}')
        self.action('prepare', '--actor', 'host-1', '--brief-file', str(self.runtime / 'brief.json'), ok=False)
        self.prepare()
        (self.repo / 'uncommitted.txt').write_text('Unfinished work')
        self.action('launch', '--actor', 'host-1', ok=False)

    def test_worktree_cannot_create_a_competing_chain(self):
        self.start()
        worktree = self.repo / '_pm/other'
        self.git('worktree', 'add', '-qb', 'other', str(worktree))
        p = subprocess.run(['python3', str(SCRIPT), '--root', str(worktree), 'status'],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('checkout', p.stderr)

    def test_context_decision_uses_occupancy_or_ticket_fallback(self):
        for tokens, count, safe, expected, source in [
            (None, 1, True, 'continue', 'ticket-fallback'),
            (None, 2, True, 'rotate', 'ticket-fallback'),
            (150000, 1, True, 'rotate', 'context-occupancy'),
            (200000, 0, False, 'checkpoint', 'context-occupancy'),
            (120000, 1, True, 'continue', 'context-occupancy'),
        ]:
            args = ['boundary', '--tickets-completed', str(count)]
            if tokens is not None: args += ['--context-tokens', str(tokens)]
            if safe: args += ['--safe-boundary']
            result = self.cli(*args)
            self.assertEqual(result['decision'], expected)
            self.assertEqual(result['source'], source)

    def test_index_only_change_blocks_launch_even_when_worktree_matches_head(self):
        self.start(); self.prepare()
        path = self.repo / '.gitignore'
        original = path.read_text()
        path.write_text(original + 'staged-only\n')
        self.git('add', '.gitignore')
        path.write_text(original)
        self.action('launch', '--actor', 'host-1', ok=False)

    def test_linked_checkout_can_use_runtime_artifacts_in_common_git_directory(self):
        worktree = self.repo / '_pm/linked'
        self.git('worktree', 'add', '-qb', 'linked', str(worktree))
        self.repo = worktree
        self.current = self.open_session()
        self.start(); self.prepare()
        attempt = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        self.acknowledge(attempt)
        self.retire()
        self.assertEqual(self.action('begin', '--actor', 'host-2')['phase'], 'active')

    def test_same_outcome_can_continue_across_multiple_context_boundaries(self):
        self.start(); self.prepare(ticket='large-outcome')
        attempt = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        successor, _ = self.acknowledge(attempt)
        self.retire(); self.action('begin', '--actor', 'host-2')
        self.current = successor
        self.assertEqual(self.prepare('host-2', 'large-outcome')['phase'], 'prepared')

    def test_runtime_inputs_do_not_hide_product_changes(self):
        self.start(); self.prepare()
        brief = self.runtime / 'brief.json'
        product = self.repo / 'brief.json'
        product.write_text(brief.read_text())
        self.assertIn('unfinished changes', self.action('launch', '--actor', 'host-1', ok=False))

    def test_attempt_commands_without_handoff_return_guidance_not_tracebacks(self):
        self.start()
        original = self.action('status')
        for command, extra in [
            ('created', ['--successor', 'host-2']),
            ('acknowledge', ['--session', self.current['path'], '--id', self.current['id']]),
            ('cancel', ['--evidence-file', 'unused']),
            ('not-created', ['--evidence-file', 'unused']),
        ]:
            error = self.action(command, '--actor', 'host-1', '--attempt', 'missing', *extra, ok=False)
            self.assertIn('launch attempt mismatch', error)
            self.assertNotIn('Traceback', error)
            self.assertEqual(self.action('status'), original)

    def test_cancel_records_stopped_successor_and_prevents_late_begin(self):
        self.start(); self.prepare()
        attempt = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        self.action('created', '--actor', 'host-1', '--attempt', attempt, '--successor', 'host-2')
        (self.runtime / 'stopped.md').write_text('Fixture host confirms host-2 is stopped; no workers started.')
        cancelled = self.action('cancel', '--actor', 'host-1', '--attempt', attempt,
                                '--evidence-file', str(self.runtime / 'stopped.md'))
        self.assertEqual(cancelled['phase'], 'stopped')
        self.assertIn('host-2 is stopped', cancelled['handoff']['cancellation']['text'])
        self.action('begin', '--actor', 'host-2', ok=False)

    def test_empty_actor_and_outside_authorization_are_rejected(self):
        self.cli('start', '--policy-file', 'policy.json', '--host', 'claude', '--actor', '',
                 '--session', self.current['path'], '--id', self.current['id'], ok=False)
        self.policy['authorization_ref'] = '../outside.md'
        (self.repo / 'policy.json').write_text(json.dumps(self.policy))
        self.cli('start', '--policy-file', 'policy.json', '--host', 'claude', '--actor', 'host-1',
                 '--session', self.current['path'], '--id', self.current['id'], ok=False)

    def test_large_brief_refused_and_policy_change_still_allows_cleanup(self):
        self.start(); self.prepare()
        attempt = self.action('launch', '--actor', 'host-1')['handoff']['attempt']
        self.acknowledge(attempt)
        (self.repo / 'intent.md').write_text('Scope revoked.')
        self.retire()
        self.action('begin', '--actor', 'host-2', ok=False)
        self.action('cancel', '--actor', 'host-1', '--attempt', attempt, '--evidence-file', str(self.runtime / 'resources.md'))
        # A new explicitly opted-in fixture run gets a fresh bound session.
        self.current = self.open_session(); self.start(); self.close_session(self.current)
        (self.runtime / 'oversize.json').write_text(json.dumps({'summary': 'x' * 12001}))
        self.assertIn('compact', self.action('prepare', '--actor', 'host-1',
                                            '--brief-file', str(self.runtime / 'oversize.json'), ok=False))


if __name__ == '__main__':
    unittest.main()
