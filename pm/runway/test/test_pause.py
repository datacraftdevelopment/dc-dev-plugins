"""Offline tests for the machine-wide pause (~/.runway/pause). Run: python3 -m pytest -q test_pause.py
RUNWAY_HOME points the pause file at a temp folder; a fake agent command stands in for `claude -p`."""
import datetime as dt
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
from test_heartbeat import make_repo, state  # noqa: E402

WORKING_AGENT = 'import sys; sys.stdin.read()\nopen("work.txt", "w").write("x")\n'

# Asks for a stop-now pause from inside the run, then would sleep. The CLI kills this process (agent_pid).
STOPPED_AGENT = '''import os, subprocess, sys, time
sys.stdin.read()
open("partial.txt", "w").write("half done")
subprocess.run([sys.executable, os.environ["RUNWAY_PY"], "--root", os.environ["HB_ROOT"], "pause", "--stop-now"], check=True)
time.sleep(60)
'''


def iso(delta):
    return (dt.datetime.now().astimezone() + delta).isoformat(timespec="seconds")


class Pause(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.pause_file = self.home / "pause"
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT", "RUNWAY_PY")}
        os.environ["RUNWAY_HOME"] = str(self.home)
        os.environ["RUNWAY_PY"] = str(Path(runway.__file__))

    def tearDown(self):
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def repo(self, agent=WORKING_AGENT, tickets=None, check="true"):
        root = make_repo(tickets or {"01-thing": ""}, check=check)
        (root / "fake_agent.py").write_text(agent)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "agent"], cwd=root, check=True, capture_output=True)
        os.environ["HB_ROOT"] = str(root)
        return root

    def cfg(self, root):
        return dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))

    def cli(self, root, *args):
        return subprocess.run([sys.executable, str(Path(runway.__file__)), "--root", str(root), *args],
                              capture_output=True, text=True, env=dict(os.environ))

    def tick(self, root):
        cfg = self.cfg(root)
        return runway.tick(cfg, root, runway.make_tracker(cfg, root))

    def write_pause(self, until, mode="finish"):
        self.pause_file.write_text(json.dumps({"until": until, "mode": mode, "at": iso(dt.timedelta())}))

    def ticket_text(self, root):
        return (root / ".scratch" / "eff" / "issues" / "01-thing.md").read_text()

    def log_text(self, root):
        return (root / "_pm" / "runway.log").read_text()

    # -- the pause / resume commands --

    def test_pause_writes_file_and_resume_deletes_it(self):
        root = self.repo()
        r = self.cli(root, "pause")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(self.pause_file.read_text())
        self.assertEqual(set(p), {"until", "mode", "at"})
        self.assertIsNone(p["until"])
        self.assertEqual(p["mode"], "finish")
        self.assertRegex(p["at"], r"^\d{4}-\d\d-\d\dT")
        self.assertEqual(self.cli(root, "resume").returncode, 0)
        self.assertFalse(self.pause_file.exists())
        self.assertEqual(self.cli(root, "resume").returncode, 0)  # nothing to resume is fine

    def test_pause_for_and_until(self):
        root = self.repo()
        self.cli(root, "pause", "--for", "1h")
        until = dt.datetime.fromisoformat(json.loads(self.pause_file.read_text())["until"])
        left = (until - dt.datetime.now().astimezone()).total_seconds()
        self.assertTrue(3500 < left <= 3600, left)
        self.cli(root, "pause", "--until", "2099-01-02T03:04:05+00:00")
        self.assertEqual(json.loads(self.pause_file.read_text())["until"], "2099-01-02T03:04:05+00:00")

    def test_pause_rejects_bad_times(self):
        root = self.repo()
        self.assertNotEqual(self.cli(root, "pause", "--for", "soon").returncode, 0)
        self.assertNotEqual(self.cli(root, "pause", "--until", "tomorrow-ish").returncode, 0)
        self.assertFalse(self.pause_file.exists())

    def test_stop_now_sets_stop_mode(self):
        root = self.repo()
        self.cli(root, "pause", "--stop-now")
        self.assertEqual(json.loads(self.pause_file.read_text())["mode"], "stop")

    # -- finish mode and expiry --

    def test_paused_tick_exits_early_and_logs(self):
        root = self.repo()
        until = iso(dt.timedelta(hours=1))
        self.write_pause(until)
        self.assertFalse(self.tick(root))
        self.assertIn(f"paused until {until}", self.log_text(root))
        self.assertEqual(state(root)["phase"], "paused")
        self.assertNotIn("Status: claimed", self.ticket_text(root))
        self.assertFalse((root / "work.txt").exists())
        self.assertTrue(self.pause_file.exists())

    def test_paused_without_end_says_so(self):
        root = self.repo()
        self.write_pause(None)
        self.tick(root)
        self.assertIn("paused until resumed", self.log_text(root))

    def test_expired_pause_clears_itself_and_work_runs(self):
        root = self.repo()
        self.write_pause(iso(-dt.timedelta(minutes=1)))
        self.assertTrue(self.tick(root))
        self.assertFalse(self.pause_file.exists())
        self.assertIn("Status: resolved", self.ticket_text(root))

    def test_loop_pauses_between_ticks_and_skips_finish(self):
        root = self.repo(tickets={"01-thing": "", "02-next": ""})
        # Pause appears while ticket 01 runs; ticket 02 must not start.
        self.repo_agent_pauses(root)
        r = self.cli(root, "loop")
        self.assertEqual(r.returncode, 0, r.stderr)
        issues = root / ".scratch" / "eff" / "issues"
        self.assertIn("Status: resolved", (issues / "01-thing.md").read_text())
        self.assertNotIn("Status: claimed", (issues / "02-next.md").read_text())
        self.assertNotIn("Status: resolved", (issues / "02-next.md").read_text())
        self.assertIn("paused until", self.log_text(root))
        self.assertEqual(state(root)["phase"], "idle")  # the exiting loop leaves no stale "paused" under a dead pid
        self.assertFalse((root / "_pm" / "runway-pr.md").exists())

    def repo_agent_pauses(self, root):
        (root / "fake_agent.py").write_text(
            'import os, subprocess, sys\nsys.stdin.read()\nopen("work.txt", "w").write("x")\n'
            'subprocess.run([sys.executable, os.environ["RUNWAY_PY"], "--root", os.environ["HB_ROOT"], "pause"], check=True)\n')
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "agent"], cwd=root, check=True, capture_output=True)

    def test_finish_mode_lets_running_ticket_finish(self):
        root = self.repo(tickets={"01-thing": "", "02-next": ""})
        self.repo_agent_pauses(root)
        cfg = self.cfg(root)
        self.assertTrue(runway.tick(cfg, root, runway.make_tracker(cfg, root)))  # runs 01, pause lands mid-run
        self.assertTrue(self.pause_file.exists())
        self.assertEqual(json.loads(self.pause_file.read_text())["mode"], "finish")
        self.assertIn("Status: resolved", self.ticket_text(root))  # 01 finished and merged

    def test_status_json_reports_pause(self):
        root = self.repo()
        self.assertIsNone(json.loads(self.cli(root, "status", "--json").stdout)["paused"])
        self.cli(root, "pause", "--for", "1h")
        p = json.loads(self.cli(root, "status", "--json").stdout)["paused"]
        self.assertEqual(set(p), {"until", "mode", "at"})
        self.write_pause(iso(-dt.timedelta(minutes=1)))
        self.assertIsNone(json.loads(self.cli(root, "status", "--json").stdout)["paused"])

    # -- stop mode --

    def test_stop_now_ends_agent_and_returns_ticket_to_ready_keeping_worktree(self):
        root = self.repo(agent=STOPPED_AGENT)
        self.tick(root)
        text = self.ticket_text(root)
        self.assertIn("Status: ready", text)
        self.assertIn("stopped by pause", text)
        self.assertNotIn("Claimed-by", text)
        self.assertNotIn("needs-human", text)
        wt = (runway.worktrees(self.cfg(root), root) / "eff-01-thing")
        self.assertTrue((wt / "partial.txt").exists(), "worktree must survive the stop")
        self.assertTrue(self.pause_file.exists())
        self.assertIsNone(state(root)["agent_pid"])
        # Ticket is not merged, and the next tick stays out of it while paused.
        self.assertNotIn("Status: resolved", text)
        self.assertFalse(self.tick(root))

    def test_stop_now_without_root_stops_agents_in_every_repo(self):
        import threading
        import time
        agent = "import sys, time\nsys.stdin.read()\nopen('partial.txt', 'w').write('x')\ntime.sleep(60)\n"
        a, b = self.repo(agent=agent), self.repo(agent=agent)
        ticks = [threading.Thread(target=self.tick, args=(r,)) for r in (a, b)]
        for t in ticks:
            t.start()
        deadline = time.time() + 30
        while time.time() < deadline and len(list((self.home / "agents").glob("*"))) < 2:
            time.sleep(0.1)
        self.assertEqual(len(list((self.home / "agents").glob("*"))), 2, "both agents should be running")
        elsewhere = tempfile.mkdtemp()  # no --root, and cwd is neither repo
        r = subprocess.run([sys.executable, str(Path(runway.__file__)), "pause", "--stop-now"],
                           capture_output=True, text=True, env=dict(os.environ), cwd=elsewhere)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("no agent running", r.stdout)
        for t in ticks:
            t.join(30)
            self.assertFalse(t.is_alive(), "tick should end once its agent is stopped")
        for root in (a, b):
            text = self.ticket_text(root)
            self.assertIn("Status: ready", text)
            self.assertIn("stopped by pause", text)
            self.assertNotIn("Claimed-by", text)

    def test_stop_now_leaves_a_reused_pid_alone(self):
        import time
        bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            (self.home / "agents").mkdir(parents=True, exist_ok=True)
            # A registration whose recorded start time is not this process's: the pid was reused.
            (self.home / "agents" / str(bystander.pid)).write_text("/tmp/repo\nMon Jan  1 00:00:00 2001\n")
            r = self.cli(self.repo(), "pause", "--stop-now")
            self.assertEqual(r.returncode, 0, r.stderr)
            time.sleep(0.3)
            self.assertIsNone(bystander.poll(), "an unrelated process must not be signalled")
            self.assertIn("left alone", r.stdout)
        finally:
            bystander.kill()
            bystander.wait()

    def test_stop_now_without_running_agent_just_pauses(self):
        root = self.repo()
        r = self.cli(root, "pause", "--stop-now")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.pause_file.read_text())["mode"], "stop")


if __name__ == "__main__":
    unittest.main()
