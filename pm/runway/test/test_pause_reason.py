"""Offline tests: the pause's reason, and `runway resume --if-reason`. Run: python3 -m pytest -q test_pause_reason.py"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
import test_pause  # noqa: E402



class PauseReason(unittest.TestCase):
    # borrow Pause's fixtures without re-running its tests
    _p = test_pause.Pause
    setUp, tearDown, repo, cfg, cli = _p.setUp, _p.tearDown, _p.repo, _p.cfg, _p.cli
    del _p

    def test_pause_for_auth_writes_reason_and_status_carries_it(self):
        root = self.repo()
        cfg = self.cfg(root)
        runway.pause_for_auth(cfg, root)
        self.assertEqual(json.loads(self.pause_file.read_text())["reason"], "signed-out")
        paused = runway.status_json(cfg, root, runway.make_tracker(cfg, root))["paused"]
        self.assertEqual(paused["reason"], "signed-out")

    def test_plain_pause_has_no_reason(self):
        root = self.repo()
        self.cli(root, "pause")
        self.assertNotIn("reason", json.loads(self.pause_file.read_text()))

    def test_resume_if_reason_leaves_a_hand_set_pause(self):
        root = self.repo()
        self.cli(root, "pause")
        r = self.cli(root, "resume", "--if-reason", "signed-out")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.pause_file.exists())
        self.assertIn("left", r.stdout)

    def test_resume_if_reason_clears_a_sign_in_pause(self):
        root = self.repo()
        runway.pause_for_auth(self.cfg(root), root)
        r = self.cli(root, "resume", "--if-reason", "signed-out")
        self.assertFalse(self.pause_file.exists())
        self.assertIn("resumed", r.stdout)

    def test_resume_if_reason_with_no_pause(self):
        root = self.repo()
        r = self.cli(root, "resume", "--if-reason", "signed-out")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no pause", r.stdout)

    def test_plain_resume_still_clears_any_pause(self):
        root = self.repo()
        runway.pause_for_auth(self.cfg(root), root)
        self.cli(root, "resume")
        self.assertFalse(self.pause_file.exists())


if __name__ == "__main__":
    unittest.main()
