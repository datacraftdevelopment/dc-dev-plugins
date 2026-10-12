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

    def test_a_pause_replaced_while_resuming_is_kept(self):
        # Joe's pause lands between resume reading the sign-in pause and removing it.
        root = self.repo()
        self.cli(root, "pause")
        mine = self.pause_file.read_text()
        old = runway.active_pause
        runway.active_pause = lambda clean=True: {"reason": "signed-out", "until": None}
        try:
            runway.cmd_resume("signed-out")
        finally:
            runway.active_pause = old
        self.assertEqual(self.pause_file.read_text(), mine)
        self.assertEqual(sorted(x.name for x in self.pause_file.parent.iterdir() if x.name.startswith("pause.")),
                         ["pause.lock"])

    def test_the_pause_stays_in_force_while_a_removal_checks_it(self):
        root = self.repo()
        self.cli(root, "pause")
        seen = []

        def matches(data):  # runs mid-removal: an observer must still see the pause
            seen.append(runway.active_pause(clean=False))
            return False
        self.assertFalse(runway.remove_pause_if(matches))
        self.assertIsNotNone(seen[0])
        self.assertIsNotNone(runway.active_pause(clean=False))

    def test_an_interrupted_removal_leaves_the_pause_in_place(self):
        root = self.repo()
        runway.pause_for_auth(self.cfg(root), root)

        def interrupted(data):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            runway.remove_pause_if(interrupted)
        self.assertEqual(runway.active_pause(clean=False)["reason"], "signed-out")

    def test_expiry_cleanup_keeps_a_pause_written_just_before_it(self):
        # active_pause read an expired pause; Joe's stop lands before the cleanup removes it.
        root = self.repo()
        runway.write_pause(runway.dt.datetime.now().astimezone() - runway.dt.timedelta(minutes=5), "finish")
        real = runway.pause_expired
        calls = []

        def expired_then_replaced(data):
            calls.append(1)
            if len(calls) == 1:  # the first look, in active_pause: the old pause, expired
                runway.write_pause(None, "stop")
            return real(data)
        runway.pause_expired = expired_then_replaced
        try:
            seen = runway.active_pause()
        finally:
            runway.pause_expired = real
        self.assertEqual(seen["mode"], "stop")  # this very call reports the stop now in force
        self.assertTrue(runway.stop_requested())
        self.assertEqual(runway.active_pause(clean=False)["mode"], "stop")

    def test_expired_pause_is_still_cleaned_up(self):
        root = self.repo()
        runway.write_pause(runway.dt.datetime.now().astimezone() - runway.dt.timedelta(minutes=5), "finish")
        self.assertIsNone(runway.active_pause())
        self.assertFalse(self.pause_file.exists())

    def test_pause_writes_wait_for_the_lock(self):
        import subprocess, time
        root = self.repo()
        lock = str(self.pause_file) + ".lock"
        holder = subprocess.Popen([sys.executable, "-c",
                                   "import fcntl,os,sys,time; fd=os.open(sys.argv[1], os.O_RDWR|os.O_CREAT); "
                                   "fcntl.flock(fd, fcntl.LOCK_EX); print('held', flush=True); time.sleep(1)", lock],
                                  stdout=subprocess.PIPE, text=True)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        start = time.monotonic()
        runway.write_pause(None, "finish")
        self.assertGreater(time.monotonic() - start, 0.5)
        holder.wait()


if __name__ == "__main__":
    unittest.main()
