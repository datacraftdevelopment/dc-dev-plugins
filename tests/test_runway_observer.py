import importlib.util
import json
import plistlib
import tempfile
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location('observer', Path(__file__).parents[1] / 'factory/scripts/observe.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
service_spec = importlib.util.spec_from_file_location('observer_service', Path(__file__).parents[1] / 'factory/scripts/observer_service.py')
service = importlib.util.module_from_spec(service_spec)
service_spec.loader.exec_module(service)


class ObserverTests(unittest.TestCase):
    def test_crash_between_state_commit_and_projection_recovers_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pm = root / '_pm'
            pm.mkdir()
            (pm / 'runway-runs.jsonl').write_text(json.dumps({'kind': 'finish', 'check_exit': 1}) + '\n')
            original = observer.atomic_write
            def fail_projection(path, text):
                if path.name == 'events.jsonl':
                    raise OSError('simulated interrupted export')
                return original(path, text)
            with patch.object(observer, 'atomic_write', side_effect=fail_projection):
                with self.assertRaises(OSError):
                    observer.tick(root, pm / 'observer')
            self.assertEqual(observer.tick(root, pm / 'observer'), [])
            queue = (pm / 'observer/events.jsonl').read_text().splitlines()
            self.assertEqual(len(queue), 1)
            self.assertEqual(len(json.loads((pm / 'observer/state.json').read_text())['packets']), 1)

    def test_state_write_failure_does_not_publish_or_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pm = root / '_pm'
            pm.mkdir()
            (pm / 'runway-runs.jsonl').write_text(json.dumps({'kind': 'finish', 'check_exit': 1}) + '\n')
            with patch.object(observer, 'atomic_write', side_effect=OSError('state failure')):
                with self.assertRaises(OSError):
                    observer.tick(root, pm / 'observer')
            self.assertFalse((pm / 'observer/events.jsonl').exists())
            self.assertEqual(len(observer.tick(root, pm / 'observer')), 1)
            self.assertEqual(observer.tick(root, pm / 'observer'), [])

    def test_baseline_boundary_survives_500_record_batches(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pm = root / '_pm'
            pm.mkdir()
            path = pm / 'runway-runs.jsonl'
            path.write_text(''.join(json.dumps({'kind': 'finish', 'ticket': str(n)}) + '\n' for n in range(501)))
            first = observer.tick(root, pm / 'observer')
            with path.open('a') as stream:
                stream.write(json.dumps({'kind': 'finish', 'ticket': 'new'}) + '\n')
            second = observer.tick(root, pm / 'observer')
            self.assertEqual(len(first), 500)
            self.assertTrue(all(p['baseline'] for p in first))
            self.assertTrue(second[0]['baseline'])
            self.assertFalse(second[1]['baseline'])

    def test_queue_and_service_logs_have_bounded_retention(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pm = root / '_pm'
            pm.mkdir()
            path = pm / 'runway-runs.jsonl'
            path.write_text(''.join(json.dumps({'kind': 'finish', 'ticket': str(n)}) + '\n' for n in range(8)))
            with patch.object(observer, 'MAX_PACKETS', 3), patch.object(observer, 'MAX_QUEUE_BYTES', 4000):
                observer.tick(root, pm / 'observer')
                packets = [json.loads(x) for x in (pm / 'observer/events.jsonl').read_text().splitlines()]
                self.assertLessEqual(len(packets), 3)
                self.assertLessEqual((pm / 'observer/events.jsonl').stat().st_size, 4000)
                self.assertEqual(packets[-1]['event']['ticket'], '7')
            with patch.object(observer, 'MAX_PACKETS', 1000), patch.object(observer, 'MAX_QUEUE_BYTES', 1000):
                observer.tick(root, pm / 'observer')
                self.assertLessEqual((pm / 'observer/events.jsonl').stat().st_size, 1000)
                self.assertLess(len(json.loads((pm / 'observer/state.json').read_text())['packets']), 3)
            logger = observer.service_logger(pm / 'observer', max_bytes=256)
            try:
                for _ in range(50):
                    logger.error('x' * 100)
            finally:
                for handler in logger.handlers:
                    handler.close()
            for name in ['service.log', 'service-error.log']:
                logs = list((pm / 'observer').glob(name + '*'))
                self.assertEqual(len(logs), 3)
                self.assertTrue(all(p.stat().st_size <= 256 for p in logs))
            self.assertEqual(path.read_text().count('\n'), 8)  # Runway log untouched

    def test_absent_service_uninstall_and_permission_errors(self):
        absent = subprocess.CompletedProcess(['launchctl', 'print'], 113, '', 'Could not find service "observer"')
        with patch.object(service.subprocess, 'run', return_value=absent) as run:
            service.unload('gui/501/observer')
            self.assertEqual(run.call_count, 1)
        denied = subprocess.CompletedProcess(['launchctl', 'print'], 1, '', 'Operation not permitted')
        with patch.object(service.subprocess, 'run', return_value=denied):
            with self.assertRaises(subprocess.CalledProcessError):
                service.unload('gui/501/observer')

    def test_unloaded_or_failed_bootstrap_plist_can_be_removed_and_reinstalled(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            root = home / 'repo'
            root.mkdir()
            (root / 'runway.json').write_text('{}')
            path = home / 'Library/LaunchAgents/com.joe.runway.observer.dc-dev-plugins.plist'
            path.parent.mkdir(parents=True)
            path.write_bytes(plistlib.dumps(service.manifest(root)))
            absent = subprocess.CompletedProcess(['launchctl', 'print'], 113, '', 'Could not find service "observer"')
            with patch.object(service.Path, 'home', return_value=home), patch.object(service.sys, 'argv', ['service', 'uninstall', '--root', str(root)]), patch.object(service.subprocess, 'run', return_value=absent):
                service.main()
            self.assertFalse(path.exists())
            with patch.object(service.Path, 'home', return_value=home), patch.object(service.sys, 'argv', ['service', 'install', '--root', str(root)]), patch.object(service.subprocess, 'run', return_value=subprocess.CompletedProcess(['launchctl'], 0)):
                service.main()
            self.assertTrue(path.exists())

    def test_bootout_race_is_reconciled_but_other_errors_are_not(self):
        present = subprocess.CompletedProcess(['launchctl', 'print'], 0, '', '')
        absent = subprocess.CompletedProcess(['launchctl', 'print'], 113, '', 'Could not find service "observer"')
        failure = subprocess.CompletedProcess(['launchctl', 'bootout'], 3, '', 'No such process')
        with patch.object(service.subprocess, 'run', side_effect=[present, failure, absent]):
            service.unload('gui/501/observer')
        denied = subprocess.CompletedProcess(['launchctl', 'print'], 1, '', 'Operation not permitted')
        with patch.object(service.subprocess, 'run', side_effect=[present, failure, denied]):
            with self.assertRaises(subprocess.CalledProcessError):
                service.unload('gui/501/observer')

    def test_service_is_scoped_and_does_not_start_runner(self):
        self.assertEqual(service.manifest(Path('/tmp/example'))['ProgramArguments'][-1], '600')
        data = service.manifest(Path('/tmp/example'), 45)
        self.assertEqual(data['Label'], 'com.joe.runway.observer.dc-dev-plugins')
        self.assertIn('observe.py', data['ProgramArguments'][1])
        self.assertNotIn('loop', data['ProgramArguments'])
        self.assertEqual(data['ProgramArguments'][-1], '45')

    def test_bad_and_oversized_records_do_not_block_later_finish(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pm = root / '_pm'
            pm.mkdir()
            (pm / 'runway-state.json').write_text('[]')
            (pm / 'runway-runs.jsonl').write_text('[]\n' + 'x' * 70000 + '\n' + json.dumps({'kind': 'finish', 'check_exit': 1}) + '\n')
            self.assertEqual(len(observer.tick(root, pm / 'observer')), 1)

    def test_completed_failure_dedup_restart_and_partial_record(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pm = root / '_pm'
            pm.mkdir()
            path = pm / 'runway-runs.jsonl'
            line = json.dumps({'kind': 'finish', 'check_exit': 1, 'pr': 'example'})
            path.write_text(line)
            self.assertEqual(observer.tick(root, pm / 'observer'), [])
            with path.open('a') as stream:
                stream.write('\n')
            self.assertEqual(len(observer.tick(root, pm / 'observer')), 1)
            self.assertEqual(observer.tick(root, pm / 'observer'), [])
            self.assertEqual(len((pm / 'observer/events.jsonl').read_text().splitlines()), 1)

    def test_wait_reason_change_and_old_active_phase(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pm = root / '_pm'
            pm.mkdir()
            path = pm / 'runway-state.json'
            path.write_text(json.dumps({'phase': 'agent', 'since': '2000-01-01'}))
            packets = observer.tick(root, pm / 'observer')
            self.assertEqual(packets[0]['event']['kind'], 'overdue')
            self.assertEqual(packets[0]['liveness'], 'unverified')
            path.write_text(json.dumps({'phase': 'waiting', 'reason': 'auth'}))
            self.assertEqual(len(observer.tick(root, pm / 'observer')), 1)
            self.assertEqual(observer.tick(root, pm / 'observer'), [])
            path.write_text(json.dumps({'phase': 'waiting', 'reason': 'auth', 'since': 'new tick'}))
            self.assertEqual(observer.tick(root, pm / 'observer'), [])
            path.write_text(json.dumps({'phase': 'waiting', 'reason': 'tracker'}))
            self.assertEqual(len(observer.tick(root, pm / 'observer')), 1)


if __name__ == '__main__':
    unittest.main()
