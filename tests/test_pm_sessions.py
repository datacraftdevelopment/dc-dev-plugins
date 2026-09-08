import concurrent.futures
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'pm/scripts/session.py'


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)

    def run_cli(self, *args, ok=True):
        p = subprocess.run(['python3', str(SCRIPT), '--root', str(self.repo), *args],
                           capture_output=True, text=True)
        if ok: self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout) if ok else p

    def open(self):
        return self.run_cli('open', '--name', 'joe', '--intent', 'Test session identity.')

    def test_concurrent_allocation_and_reverse_idempotent_close(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            sessions = list(pool.map(lambda _: self.open(), range(4)))
        self.assertEqual(len({s['path'] for s in sessions}), 4)
        for s in reversed(sessions):
            result = self.run_cli('close', '--session', s['path'], '--id', s['id'], '--entry', 'Verified '+s['id'])
            self.assertEqual(result['status'], 'closed')
            before = (self.repo / s['path']).read_bytes()
            again = self.run_cli('close', '--session', s['path'], '--id', s['id'], '--entry', 'duplicate')
            self.assertEqual(again['status'], 'already-closed')
            self.assertEqual((self.repo / s['path']).read_bytes(), before)
            self.assertEqual(before.count(b'Closed: '), 1)

    def test_id_mismatch_refuses_to_touch_other_session(self):
        first, second = self.open(), self.open()
        original = (self.repo / second['path']).read_bytes()
        p = self.run_cli('close', '--session', second['path'], '--id', first['id'], '--entry', 'oops', ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((self.repo / second['path']).read_bytes(), original)

    def test_reaim_is_append_only_and_closed_refuses(self):
        s = self.open()
        path = self.repo / s['path']; before = path.read_text()
        self.run_cli('reaim', '--session', s['path'], '--id', s['id'], '--entry', 'New aim')
        self.assertTrue(path.read_text().startswith(before))
        self.assertIn('New aim', path.read_text())
        self.run_cli('close', '--session', s['path'], '--id', s['id'], '--entry', 'finished')
        p = self.run_cli('reaim', '--session', s['path'], '--id', s['id'], '--entry', 'late', ok=False)
        self.assertNotEqual(p.returncode, 0)

    def test_path_escape_and_invalid_name_refused(self):
        p = self.run_cli('open', '--name', '../escape', '--intent', 'no', ok=False)
        self.assertNotEqual(p.returncode, 0)
        p = self.run_cli('close', '--session', '../outside', '--id', 'anything', '--entry', 'no', ok=False)
        self.assertNotEqual(p.returncode, 0)
