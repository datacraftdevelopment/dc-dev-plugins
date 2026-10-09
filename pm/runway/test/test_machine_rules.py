"""Offline tests for the per-Mac quiet-time rules (~/.runway/machine.json). Run: python3 -m pytest -q test_machine_rules.py
RUNWAY_HOME points at a temp folder; clock, battery, idle and the agent count are swapped for fakes."""
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

MON_10AM = dt.datetime(2026, 10, 5, 10, 0).astimezone()  # a Monday
MON_8PM = dt.datetime(2026, 10, 5, 20, 0).astimezone()
SAT_10AM = dt.datetime(2026, 10, 10, 10, 0).astimezone()

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri"]
QUIET = {"enabled": True, "from": "09:00", "to": "17:00", "days": WEEKDAYS}


def rules(**kw):
    return dict({"version": 1}, **kw)


class Machine(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT")}
        os.environ["RUNWAY_HOME"] = str(self.home)
        self._orig = {n: getattr(runway, n) for n in ("read_clock", "read_on_battery", "read_idle_seconds")}
        self.clock, self.battery, self.idle = MON_8PM, False, 9999.0
        runway.read_clock = lambda: self.clock
        runway.read_on_battery = lambda: self.battery
        runway.read_idle_seconds = lambda: self.idle

    def tearDown(self):
        for n, f in self._orig.items():
            setattr(runway, n, f)
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def write(self, data):
        (self.home / "machine.json").write_text(json.dumps(data) if not isinstance(data, str) else data)

    def block(self):
        return runway.machine_block()

    # -- the rules, one by one --

    def test_missing_file_means_no_rules(self):
        self.assertIsNone(self.block())
        self.assertEqual(runway.load_machine_rules(), {})

    def test_quiet_hours_block_inside_window(self):
        self.write(rules(quiet_hours=QUIET))
        self.clock = MON_10AM
        self.assertIn("quiet hours", self.block())

    def test_quiet_hours_allow_outside_window_and_off_days(self):
        self.write(rules(quiet_hours=QUIET))
        self.clock = MON_8PM
        self.assertIsNone(self.block())
        self.clock = SAT_10AM
        self.assertIsNone(self.block())

    def test_quiet_hours_disabled(self):
        self.write(rules(quiet_hours=dict(QUIET, enabled=False)))
        self.clock = MON_10AM
        self.assertIsNone(self.block())

    def test_quiet_hours_window_wraps_midnight(self):
        self.write(rules(quiet_hours={"enabled": True, "from": "22:00", "to": "06:00", "days": ["fri"]}))
        fri_11pm = dt.datetime(2026, 10, 9, 23, 0).astimezone()
        sat_3am = dt.datetime(2026, 10, 10, 3, 0).astimezone()   # still Friday's window
        fri_3am = dt.datetime(2026, 10, 9, 3, 0).astimezone()    # Thursday's window: Thursday is not listed
        for when, blocked in ((fri_11pm, True), (sat_3am, True), (fri_3am, False)):
            self.clock = when
            self.assertEqual(self.block() is not None, blocked, when)

    def test_not_on_battery_blocks_only_on_battery(self):
        self.write(rules(not_on_battery=True))
        self.battery = True
        self.assertIn("battery", self.block())
        self.battery = False
        self.assertIsNone(self.block())

    def test_unknown_battery_does_not_block(self):
        self.write(rules(not_on_battery=True))
        runway.read_on_battery = lambda: None
        self.assertIsNone(self.block())

    def test_idle_only_needs_enough_idle_time(self):
        self.write(rules(idle_only={"enabled": True, "minutes": 10}))
        self.idle = 300.0
        self.assertIn("idle", self.block())
        self.idle = 601.0
        self.assertIsNone(self.block())

    def test_idle_only_disabled(self):
        self.write(rules(idle_only={"enabled": False, "minutes": 10}))
        self.idle = 0.0
        self.assertIsNone(self.block())

    def test_max_agents_counts_live_agents_across_repos(self):
        self.write(rules(max_agents=1))
        self.assertIsNone(self.block())
        runway.register_agent(os.getpid(), Path("/tmp/repo-a"))
        self.assertIn("max agents", self.block())
        self.assertEqual(runway.running_agents(), 1)

    def test_max_agents_ignores_dead_pids_and_cleans_up(self):
        self.write(rules(max_agents=1))
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        runway.register_agent(p.pid, Path("/tmp/repo-a"))
        self.assertIsNone(self.block())
        self.assertFalse((self.home / "agents" / str(p.pid)).exists())

    def test_unregister_agent(self):
        runway.register_agent(os.getpid(), Path("/tmp/repo-a"))
        runway.unregister_agent(os.getpid())
        self.assertEqual(runway.running_agents(), 0)

    def test_unreadable_file_blocks_rather_than_guess(self):
        self.write("{not json")
        self.assertIn("unreadable", self.block())

    # -- wired into tick / CLI --

    def repo(self):
        root = make_repo({"01-thing": ""})
        os.environ["HB_ROOT"] = str(root)
        return root

    def tick(self, root):
        cfg = dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))
        return runway.tick(cfg, root, runway.make_tracker(cfg, root))

    def test_tick_skips_logs_reason_and_sets_waiting(self):
        root = self.repo()
        self.write(rules(quiet_hours=QUIET))
        self.clock = MON_10AM
        self.assertFalse(self.tick(root))
        self.assertIn("quiet hours", (root / "_pm" / "runway.log").read_text())
        s = state(root)
        self.assertEqual(s["phase"], "waiting")
        self.assertIn("quiet hours", s["reason"])
        self.assertNotIn("claimed", (root / ".scratch/eff/issues/01-thing.md").read_text().lower())  # untouched

    def test_tick_runs_when_no_rule_blocks(self):
        root = self.repo()
        self.write(rules(quiet_hours=QUIET, not_on_battery=True))
        self.assertTrue(self.tick(root))
        self.assertTrue(list((root.parent / (root.name + "-wt")).glob("*/work.txt")))

    def test_tick_runs_with_no_machine_file(self):
        root = self.repo()
        self.assertTrue(self.tick(root))

    def test_rule_turning_on_mid_run_does_not_stop_the_agent(self):
        root = self.repo()
        self.write(rules(quiet_hours=QUIET))
        self.clock = MON_8PM
        orig = runway.run_agent

        def agent_then_quiet(*a, **k):
            self.clock = MON_10AM  # quiet hours begin while the agent works
            return orig(*a, **k)
        runway.run_agent = agent_then_quiet
        try:
            self.assertTrue(self.tick(root))
        finally:
            runway.run_agent = orig
        self.assertIn("status: resolved", (root / ".scratch/eff/issues/01-thing.md").read_text().lower())

    def test_agent_is_registered_while_running(self):
        root = self.repo()
        seen = []
        orig_sh = runway.sh

        def sh_spy(*a, **k):
            start = k.get("on_start")
            if start:
                def after_start(pid):
                    start(pid)
                    seen.append(runway.running_agents())
                k["on_start"] = after_start
            return orig_sh(*a, **k)
        runway.sh = sh_spy
        try:
            self.tick(root)
        finally:
            runway.sh = orig_sh
        self.assertIn(1, seen)  # counted while the agent ran (the registered pid is the agent's)
        self.assertEqual(runway.running_agents(), 0)  # cleaned up after the run

    def test_machine_command_reports_rules_and_verdict(self):
        root = self.repo()
        r = subprocess.run([sys.executable, str(Path(runway.__file__)), "--root", str(root), "machine"],
                           capture_output=True, text=True, env=dict(os.environ))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no rules", r.stdout)
        self.assertIn("would run", r.stdout.lower())
        self.write(rules(max_agents=0 + 1, not_on_battery=True))
        out = runway.describe_machine()
        self.assertIn("not on battery", out)
        self.assertIn("max agents", out)
        self.assertIn("would run", out.lower())
        self.write(rules(quiet_hours=QUIET))
        self.clock = MON_10AM
        out = runway.describe_machine()
        self.assertIn("would not run", out.lower())
        self.assertIn("quiet hours", out)


if __name__ == "__main__":
    unittest.main()
