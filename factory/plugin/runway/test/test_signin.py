"""Offline tests: sign-in checks before a tick starts work. Run: python3 -m pytest -q test_signin.py
Stub status commands (python one-liners) stand in for `claude auth status`, `gh auth status` and the rest."""
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

OK = f'{sys.executable} -c "print(1)"'
SIGNED_OUT = f'{sys.executable} -c "import sys; sys.exit(1)"'
# exits 0 but says it is logged out
LOGGED_IN_FALSE = [sys.executable, "-c", 'print(\'{"loggedIn": false}\')']
MISSING = "/nonexistent/claude-not-installed auth status"


class SignIn(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT")}
        os.environ["RUNWAY_HOME"] = str(self.home)

    def tearDown(self):
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def repo(self, tickets=None, claude=OK, **extra):
        root = make_repo(tickets or {"01-thing": ""})
        cfg = json.loads((root / "runway.json").read_text())
        cfg["notify_cmd"] = f"{sys.executable} -c \"import sys; open(r'{root}/notified','a').write(sys.argv[1]+chr(10))\" {{msg}}"
        cfg["signin_cmds"] = {"claude": claude, "codex": OK, "gh": OK}
        cfg.update(extra)
        (root / "runway.json").write_text(json.dumps(cfg))
        os.environ["HB_ROOT"] = str(root)
        return root

    def set_claude(self, root, cmd):
        cfg = json.loads((root / "runway.json").read_text())
        cfg["signin_cmds"]["claude"] = cmd
        (root / "runway.json").write_text(json.dumps(cfg))

    def cfg(self, root):
        return dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))

    def tick(self, root):
        cfg = self.cfg(root)
        return runway.tick(cfg, root, runway.make_tracker(cfg, root))

    def ticket(self, root):
        return (root / ".scratch" / "eff" / "issues" / "01-thing.md").read_text()

    def notified(self, root):
        p = root / "notified"
        return p.read_text().splitlines() if p.exists() else []

    def test_signed_in_runs_the_ticket(self):
        root = self.repo()
        self.tick(root)
        self.assertIn("Status: resolved", self.ticket(root))
        self.assertEqual(self.notified(root), [])

    def test_signed_out_claims_nothing_and_waits_with_reason(self):
        root = self.repo(claude=SIGNED_OUT)
        self.assertFalse(self.tick(root))
        text = self.ticket(root)
        self.assertNotIn("claimed", text.lower())
        self.assertNotIn("Status: resolved", text)
        s = state(root)
        self.assertEqual(s["phase"], "waiting")
        self.assertEqual(s["reason"], "Claude Code needs signing in (`claude auth login`)")
        self.assertIn("waiting: Claude Code needs signing in (`claude auth login`)",
                      (root / "_pm" / "runway.log").read_text())

    def test_logged_in_false_in_json_counts_as_signed_out(self):
        root = self.repo(claude=LOGGED_IN_FALSE)
        self.tick(root)
        self.assertEqual(state(root)["phase"], "waiting")

    def test_tool_missing_waits_and_says_so(self):
        root = self.repo(claude=MISSING)
        self.tick(root)
        s = state(root)
        self.assertEqual(s["phase"], "waiting")
        self.assertIn("not installed", s["reason"])
        self.assertNotIn("Status: resolved", self.ticket(root))

    def test_repeated_failing_ticks_notify_once_until_it_clears(self):
        root = self.repo(claude=SIGNED_OUT)
        for _ in range(3):
            self.tick(root)
        self.assertEqual(self.notified(root), ["Runway: Claude Code needs signing in"])
        self.set_claude(root, OK)  # Joe signs in: the next tick runs
        self.tick(root)
        self.assertIn("Status: resolved", self.ticket(root))
        (root / ".scratch" / "eff" / "issues" / "02-next.md").write_text("# Next\n\n")
        self.set_claude(root, SIGNED_OUT)  # signed out again: a fresh failure notifies again
        self.tick(root)
        self.assertEqual(len(self.notified(root)), 2)

    def test_idle_tick_runs_no_checks(self):
        root = self.repo(tickets={"01-thing": "Status: resolved"}, claude=SIGNED_OUT)
        self.tick(root)
        self.assertEqual(self.notified(root), [])
        self.assertNotEqual(state(root).get("phase"), "waiting")
        self.assertFalse((root / "_pm" / "runway-signin.json").exists())

    def test_results_are_in_status_json_and_machine_output(self):
        root = self.repo(claude=SIGNED_OUT)
        self.tick(root)
        cfg = self.cfg(root)
        doc = runway.status_json(cfg, root, runway.make_tracker(cfg, root))
        checks = {c["name"]: c for c in doc["signin"]["checks"]}
        self.assertFalse(checks["claude"]["ok"])
        self.assertFalse(doc["signin"]["ok"])
        out = runway.describe_machine(root)
        self.assertIn("claude", out)
        self.assertIn("needs signing in", out)

    def test_status_json_signin_null_before_any_check(self):
        root = self.repo()
        cfg = self.cfg(root)
        self.assertIsNone(runway.status_json(cfg, root, runway.make_tracker(cfg, root))["signin"])

    def test_gh_checked_only_when_it_will_be_used(self):
        root = self.repo()
        cfg = self.cfg(root)
        names = [c["name"] for c in runway.signin_checks(cfg, root, ["claude"])]
        self.assertEqual(names, ["claude"])
        cfg["pr"] = "draft"
        names = [c["name"] for c in runway.signin_checks(cfg, root, ["claude"], finish=True)]
        self.assertEqual(names, ["claude", "gh"])

    def test_linear_key_checked_for_linear_tracker(self):
        root = self.repo()
        cfg = self.cfg(root)
        cfg["tracker"] = "linear"
        import linear_tracker
        orig = linear_tracker.api_key
        try:
            linear_tracker.api_key = lambda c: sys.exit("No Linear API key.")
            res = {c["name"]: c for c in runway.signin_checks(cfg, root, ["claude"])}
            self.assertFalse(res["linear"]["ok"])
            linear_tracker.api_key = lambda c: "key"
            res = {c["name"]: c for c in runway.signin_checks(cfg, root, ["claude"])}
            self.assertTrue(res["linear"]["ok"])
        finally:
            linear_tracker.api_key = orig

    def test_panel_checks_both_seats(self):
        root = self.repo()
        cfg = self.cfg(root)
        names = [c["name"] for c in runway.signin_checks(cfg, root, ["claude"], panel=True)]
        self.assertEqual(names, ["claude", "codex"])

    def test_finish_waits_when_signed_out(self):
        root = self.repo(tickets={"01-thing": "Status: resolved"}, claude=SIGNED_OUT)
        git = lambda *a: subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)
        git("checkout", "-qb", "runway/integration")
        (root / "w.txt").write_text("x")
        git("add", "-A")
        git("commit", "-qm", "w")
        git("checkout", "-q", "main")
        cfg = self.cfg(root)
        self.assertFalse(runway.finish(cfg, root, runway.make_tracker(cfg, root)))
        self.assertEqual(state(root)["phase"], "waiting")
        self.assertEqual(len(self.notified(root)), 1)


if __name__ == "__main__":
    unittest.main()
