"""Offline tests: finish re-runs only when ticket work landed since the head it last reviewed.
Run: python3 -m pytest -q test_finish_skip.py
`signin_waiting` is stubbed to record the call and return True, so "finish ran" means "got past the skip
check" without launching any agent."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_heartbeat import make_repo  # noqa: E402


def git(root, *a):
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


class FinishSkip(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT")}
        os.environ["RUNWAY_HOME"] = str(self.home)
        self.root = make_repo({"01-thing": "Status: resolved"})
        os.environ["HB_ROOT"] = str(self.root)
        self.cfg = dict(runway.DEFAULT_CONFIG, **json.loads((self.root / "runway.json").read_text()))
        self.calls = 0
        self._orig = runway.signin_waiting
        runway.signin_waiting = self._stub
        git(self.root, "checkout", "-qb", "runway/integration")
        self.commit("w.txt", "ticket work")  # integration is ahead of main
        self.state_p = self.root / "_pm" / "runway-finish.json"

    def tearDown(self):
        runway.signin_waiting = self._orig
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def _stub(self, *a, **k):
        self.calls += 1
        return True

    def commit(self, name, msg):
        (self.root / name).write_text(msg)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", msg)

    def head(self):
        return git(self.root, "rev-parse", "runway/integration")

    def reviewed(self, sha=None):
        self.state_p.parent.mkdir(exist_ok=True)
        self.state_p.write_text(json.dumps({"head": sha or self.head(), "at": "x"}))

    def sync(self):
        """Move main, then merge it into integration the way sync_base does."""
        git(self.root, "checkout", "-q", "main")
        self.commit("m%d.txt" % len(list(self.root.glob("m*.txt"))), "main moved")
        git(self.root, "checkout", "-q", "runway/integration")
        git(self.root, "merge", "--no-ff", "-m", "runway: merge main into runway/integration", "main")

    def run_finish(self, force=False):
        tracker = runway.make_tracker(self.cfg, self.root)
        return runway.finish(self.cfg, self.root, tracker, force=force)

    def finish_ran(self, force=False):
        before = self.calls
        self.run_finish(force)
        return self.calls > before

    def log_text(self):
        p = self.root / "_pm" / "runway.log"
        return p.read_text() if p.exists() else ""

    def test_sync_only_skips_and_records_new_head(self):
        self.reviewed()
        self.sync()
        self.sync()
        self.assertFalse(self.finish_ran())
        self.assertEqual(json.loads(self.state_p.read_text())["head"], self.head())
        self.assertNotIn("finish runway/integration", self.log_text())

    def test_ticket_merge_after_reviewed_reruns_even_with_syncs_after(self):
        self.reviewed()
        self.commit("t.txt", "runway: merge runway/github-gh-2-y")
        self.sync()
        self.assertTrue(self.finish_ran())

    def test_hand_commit_reruns(self):
        self.reviewed()
        self.commit("h.txt", "hand fix")
        self.assertTrue(self.finish_ran())

    def test_reviewed_not_ancestor_reruns(self):
        git(self.root, "checkout", "-q", "main")
        self.commit("o.txt", "other")
        other = git(self.root, "rev-parse", "HEAD")
        git(self.root, "checkout", "-q", "runway/integration")
        self.reviewed(other)
        self.assertTrue(self.finish_ran())

    def test_missing_state_reruns(self):
        self.assertTrue(self.finish_ran())

    def test_unreadable_state_reruns(self):
        self.state_p.parent.mkdir(exist_ok=True)
        self.state_p.write_text("{not json")
        self.assertTrue(self.finish_ran())

    def test_state_without_head_reruns(self):
        self.state_p.parent.mkdir(exist_ok=True)
        self.state_p.write_text("{}")
        self.assertTrue(self.finish_ran())

    def test_forced_runs_regardless(self):
        self.reviewed()
        self.sync()
        self.assertTrue(self.finish_ran(force=True))


if __name__ == "__main__":
    unittest.main()
