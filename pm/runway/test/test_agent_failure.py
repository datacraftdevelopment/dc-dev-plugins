"""Offline tests: an agent that never ran must not count as done. Run: python3 -m pytest -q test_agent_failure.py
A fake agent command stands in for `claude -p`; RUNWAY_HOME points the pause file at a temp folder."""
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

# Each fake agent prints what `claude -p --output-format json` would.
EXIT_ONE = 'import sys; sys.stdin.read(); print("boom on stdout"); sys.stderr.write("boom on stderr"); sys.exit(1)\n'
IS_ERROR = ('import sys, json; sys.stdin.read()\n'
            'print(json.dumps({"result": "API Error: overloaded", "is_error": True, "num_turns": 3,\n'
            '                  "usage": {"output_tokens": 50}, "session_id": "s"}))\n')
ZERO_WORK = ('import sys, json; sys.stdin.read()\n'
             'print(json.dumps({"result": "", "is_error": False, "num_turns": 0,\n'
             '                  "usage": {"input_tokens": 0, "output_tokens": 0}, "session_id": "s"}))\n')
AUTH = ('import sys, json; sys.stdin.read()\n'
        'print(json.dumps({"result": "OAuth session expired and could not be refreshed", "is_error": True,\n'
        '                  "subtype": "authentication_failed", "num_turns": 0, "usage": {"output_tokens": 0}}))\n'
        'sys.exit(1)\n')
NOTHING = 'import sys; sys.stdin.read()\n'  # exits 0, changes nothing
GOOD_JSON = ('import sys, json; sys.stdin.read(); open("work.txt", "w").write("x")\n'
             'print(json.dumps({"result": "ok", "is_error": False, "num_turns": 4, "usage": {"output_tokens": 200}}))\n')


class AgentFailure(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT")}
        os.environ["RUNWAY_HOME"] = str(self.home)

    def tearDown(self):
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def repo(self, agent, tickets=None, notes=None):
        root = make_repo(tickets or {"01-thing": ""})
        (root / "fake_agent.py").write_text(agent)
        cfg = json.loads((root / "runway.json").read_text())
        cfg["notify_cmd"] = f"{sys.executable} -c \"import sys; open(r'{root}/notified','a').write(sys.argv[1]+chr(10))\" {{msg}}"
        (root / "runway.json").write_text(json.dumps(cfg))
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "agent"], cwd=root, check=True, capture_output=True)
        os.environ["HB_ROOT"] = str(root)
        return root

    def cfg(self, root):
        return dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))

    def tick(self, root):
        cfg = self.cfg(root)
        return runway.tick(cfg, root, runway.make_tracker(cfg, root))

    def ticket(self, root, name="01-thing"):
        return (root / ".scratch" / "eff" / "issues" / f"{name}.md").read_text()

    def notified(self, root):
        p = root / "notified"
        return p.read_text().splitlines() if p.exists() else []

    def assertParked(self, root, *needles):
        text = self.ticket(root)
        self.assertIn("needs-human", text)
        self.assertNotIn("Status: resolved", text)
        for n in needles:
            self.assertIn(n, text)
        self.assertFalse(self.home.joinpath("pause").exists(), "a plain failure must not pause the loop")

    def test_nonzero_exit_parks_with_error_text(self):
        root = self.repo(EXIT_ONE)
        self.tick(root)
        self.assertParked(root, "boom on stderr")

    def test_is_error_result_parks_with_error_text(self):
        root = self.repo(IS_ERROR)
        self.tick(root)
        self.assertParked(root, "API Error: overloaded")

    def test_zero_turns_and_zero_output_parks(self):
        root = self.repo(ZERO_WORK)
        self.tick(root)
        self.assertParked(root, "no turns")

    def test_no_commits_parks(self):
        root = self.repo(NOTHING)
        self.tick(root)
        self.assertParked(root, "no commits")

    def test_good_run_still_done(self):
        root = self.repo(GOOD_JSON)
        self.tick(root)
        self.assertIn("Status: resolved", self.ticket(root))
        self.assertNotIn("needs-human", self.ticket(root))

    def test_auth_error_pauses_machine_and_leaves_queue(self):
        root = self.repo(AUTH, tickets={"01-thing": "", "02-other": ""})
        self.tick(root)
        pause = json.loads(self.home.joinpath("pause").read_text())
        self.assertIsNone(pause["until"])
        self.assertEqual(pause["mode"], "finish")
        self.assertEqual(self.notified(root).count("Runway: Claude Code needs signing in"), 1)
        self.assertNotIn("Status: resolved", self.ticket(root, "01-thing"))
        self.assertNotIn("needs-human", self.ticket(root, "01-thing"))
        self.assertNotIn("claimed", self.ticket(root, "02-other").lower())
        self.assertFalse(self.tick(root))  # paused: nothing more starts
        self.assertEqual(len(self.notified(root)), 1)

    def test_auth_error_does_not_overwrite_existing_pause_or_renotify(self):
        root = self.repo(AUTH)
        self.home.joinpath("pause").write_text(json.dumps({"until": None, "mode": "finish", "at": None}))
        cfg = self.cfg(root)
        runway.pause_for_auth(cfg, root)
        self.assertEqual(self.notified(root), [])

    def test_fix_pass_failure_is_logged_as_failure(self):
        root = self.repo(EXIT_ONE)
        cfg = self.cfg(root)
        cfg["fix_cmd"] = cfg["agent_cmd"]
        hp = runway.resolve_harness(cfg)
        r, _ = runway.run_agent(cfg, root, hp["agent_cmd"], root, "p", "finish", "fix", harness=hp)
        self.assertIn("boom on stderr", r.failure)
        self.assertIn("failed", runway.fix_failure_note(r.failure))
        self.assertNotIn("no changes", runway.fix_failure_note(r.failure))


if __name__ == "__main__":
    unittest.main()
