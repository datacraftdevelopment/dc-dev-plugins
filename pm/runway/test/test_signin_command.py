"""Offline tests: labels and fixes on sign-in checks, and `runway signin`. Run: python3 -m pytest -q test_signin_command.py
Stub status commands stand in for the real CLIs, as in test_signin.py."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
import test_signin  # noqa: E402
from test_signin import SIGNED_OUT  # noqa: E402



class SignInCommand(unittest.TestCase):
    # borrow SignIn's fixtures without re-running its tests
    _s = test_signin.SignIn
    setUp, tearDown, repo, cfg, tick, ticket, notified = _s.setUp, _s.tearDown, _s.repo, _s.cfg, _s.tick, _s.ticket, _s.notified
    del _s

    def cli(self, root, *args):
        return subprocess.run([sys.executable, str(Path(runway.__file__)), "--root", str(root), *args],
                              capture_output=True, text=True, env=dict(os.environ))

    def written(self, root):
        return json.loads((root / "_pm" / "runway-signin.json").read_text())

    def test_failing_check_carries_label_and_fix(self):
        root = self.repo(claude=SIGNED_OUT)
        self.tick(root)
        c = {c["name"]: c for c in self.written(root)["checks"]}["claude"]
        self.assertEqual(c["label"], "Claude Code")
        self.assertEqual(c["fix"], "claude auth login")
        self.assertEqual(c["detail"], "Claude Code needs signing in (`claude auth login`)")

    def test_passing_check_carries_label_and_fix_too(self):
        root = self.repo()
        c = runway.signin_checks(self.cfg(root), root, ["claude"])[0]
        self.assertEqual((c["label"], c["fix"]), ("Claude Code", "claude auth login"))

    def test_signin_command_fails_writes_file_and_claims_nothing(self):
        root = self.repo(claude=SIGNED_OUT)
        r = self.cli(root, "signin")
        self.assertNotEqual(r.returncode, 0)
        doc = self.written(root)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["checks"][0]["fix"], "claude auth login")
        self.assertNotIn("claimed", self.ticket(root).lower())
        self.assertEqual(self.notified(root), [])

    def test_signin_command_passes_with_exit_zero_and_json(self):
        root = self.repo()
        r = self.cli(root, "signin", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])
        self.assertTrue(self.written(root)["ok"])
        self.assertNotIn("claimed", self.ticket(root).lower())

    def test_signin_command_makes_no_model_call(self):
        root = self.repo()
        cfg = json.loads((root / "runway.json").read_text())
        cfg["agent_cmd"] = f"{sys.executable} -c \"open(r'{root}/agent-ran','w')\""
        (root / "runway.json").write_text(json.dumps(cfg))
        self.cli(root, "signin")
        self.assertFalse((root / "agent-ran").exists())

    def test_signin_command_checks_the_harness_a_ready_ticket_needs(self):
        root = self.repo(tickets={"01-thing": "Harness: codex"},
                         harnesses={"codex": {"agent_cmd": "cx", "prep_cmd": "cx", "review_cmd": "cx", "parser": "codex"}})
        cfg = json.loads((root / "runway.json").read_text())
        cfg["signin_cmds"]["codex"] = SIGNED_OUT
        (root / "runway.json").write_text(json.dumps(cfg))
        r = self.cli(root, "signin")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        names = {c["name"]: c["ok"] for c in self.written(root)["checks"]}
        self.assertEqual((names.get("claude"), names.get("codex")), (True, False))

    def test_signin_fails_closed_when_tickets_cannot_load(self):
        root = self.repo()
        r = runway.cmd_signin(self.cfg(root), root, False, [], load_error="tracker down")
        self.assertEqual(r, 1)
        doc = self.written(root)
        self.assertFalse(doc["ok"])
        self.assertIn("tracker down", {c["name"]: c for c in doc["checks"]}["tickets"]["detail"])


if __name__ == "__main__":
    unittest.main()
