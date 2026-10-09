import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('observer', Path(__file__).parents[1] / 'factory/scripts/observe.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
service_spec = importlib.util.spec_from_file_location('observer_service', Path(__file__).parents[1] / 'factory/scripts/observer_service.py')
service = importlib.util.module_from_spec(service_spec)
service_spec.loader.exec_module(service)


class ObserverTests(unittest.TestCase):
    def test_service_is_scoped_and_does_not_start_runner(self):
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
