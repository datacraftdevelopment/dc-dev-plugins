"""Offline tests for attempt(): one build attempt returns an Outcome and never touches the tracker.
Run: python3 -m pytest -q test_attempt.py. Real temp repo, fake agent commands, no tracker."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_agent_failure import AUTH, EXIT_ONE, GOOD_JSON, NOTHING  # noqa: E402
from test_heartbeat import make_repo  # noqa: E402

QUESTION = 'import sys; sys.stdin.read(); open("RUNWAY_QUESTION.md", "w").write("which one?")\n'
CONFLICT = ('import sys, json; sys.stdin.read(); open("clash.txt", "w").write("from branch")\n'
            'print(json.dumps({"result": "ok", "is_error": False, "num_turns": 4, "usage": {"output_tokens": 200}}))\n')


class Attempt(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT")}
        os.environ["RUNWAY_HOME"] = str(self.home)

    def tearDown(self):
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def repo(self, agent, **cfg_over):
        root = make_repo({"01-thing": ""})
        (root / "fake_agent.py").write_text(agent)
        cfg = json.loads((root / "runway.json").read_text())
        cfg.update(cfg_over)
        (root / "runway.json").write_text(json.dumps(cfg))
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "agent"], cwd=root, check=True, capture_output=True)
        os.environ["HB_ROOT"] = str(root)
        cfg = dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))
        runway.ensure_integration(cfg, root)
        return root, cfg

    def run_attempt(self, root, cfg):
        t = SimpleNamespace(id="01-thing", title="Thing", ref="01-thing.md", text="do it", effort="eff", slug="thing")
        return runway.attempt(cfg, root, t)

    def test_merged(self):
        root, cfg = self.repo(GOOD_JSON)
        o = self.run_attempt(root, cfg)
        self.assertIsInstance(o, runway.Outcome)
        self.assertEqual((o.kind, o.attempts), ("merged", 1))
        files = subprocess.run(["git", "ls-tree", "-r", "--name-only", cfg["integration_branch"]], cwd=root,
                               capture_output=True, text=True).stdout
        self.assertIn("work.txt", files)

    def test_check_failed(self):
        root, cfg = self.repo(GOOD_JSON, check_cmd="false", max_attempts=2)
        o = self.run_attempt(root, cfg)
        self.assertEqual((o.kind, o.attempts), ("check-failed", 2))
        self.assertIn("Check failed on attempt 2", o.detail)

    def test_no_commits(self):
        root, cfg = self.repo(NOTHING)
        o = self.run_attempt(root, cfg)
        self.assertEqual((o.kind, o.attempts), ("no-commits", 1))
        self.assertIn("no commits", o.detail)

    def test_agent_failed(self):
        root, cfg = self.repo(EXIT_ONE)
        o = self.run_attempt(root, cfg)
        self.assertEqual((o.kind, o.attempts), ("agent-failed", 1))
        self.assertIn("boom on stderr", o.detail)

    def test_no_attempts_allowed_is_agent_failed_with_no_detail(self):
        root, cfg = self.repo(GOOD_JSON, max_attempts=0)
        o = self.run_attempt(root, cfg)
        self.assertEqual((o.kind, o.attempts, o.detail), ("agent-failed", 0, "Agent run failed with no detail."))

    def test_question(self):
        root, cfg = self.repo(QUESTION)
        o = self.run_attempt(root, cfg)
        self.assertEqual((o.kind, o.attempts), ("question", 1))
        self.assertIn("which one?", o.detail)

    def test_signed_out(self):
        root, cfg = self.repo(AUTH)
        o = self.run_attempt(root, cfg)
        self.assertEqual((o.kind, o.attempts), ("signed-out", 1))
        self.assertTrue(self.home.joinpath("pause").exists())

    def test_stopped_before_first_agent_call_reports_attempt_one(self):
        root, cfg = self.repo(GOOD_JSON)
        orig = runway.stop_requested
        runway.stop_requested = lambda: True
        try:
            o = self.run_attempt(root, cfg)
        finally:
            runway.stop_requested = orig
        self.assertEqual((o.kind, o.attempts), ("stopped", 1))

    def test_merge_conflict(self):
        root, cfg = self.repo(CONFLICT)
        orig = runway.merge_into_integration
        runway.merge_into_integration = lambda *a, **k: False
        try:
            o = self.run_attempt(root, cfg)
        finally:
            runway.merge_into_integration = orig
        self.assertEqual((o.kind, o.attempts), ("merge-conflict", 1))
        self.assertIn("did not merge cleanly", o.detail)


if __name__ == "__main__":
    unittest.main()
