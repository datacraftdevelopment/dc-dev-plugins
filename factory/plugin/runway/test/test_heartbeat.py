"""Offline tests for the heartbeat file (_pm/runway-state.json). Run: python3 -m pytest -q test_heartbeat.py
A fake agent command stands in for `claude -p`; every write of the state file is captured."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402

FAKE_AGENT = '''import json, os, sys
root = os.environ["HB_ROOT"]
sys.stdin.read()
state = json.load(open(os.path.join(root, "_pm", "runway-state.json")))
with open(os.path.join(root, "seen.jsonl"), "a") as f:
    f.write(json.dumps({"pid": os.getpid(), "state": state}) + "\\n")
if os.environ.get("HB_BREAK"):
    open("broken.txt", "w").write("x")
else:
    open("work.txt", "w").write("x")
'''


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def make_repo(tickets, check="true"):
    root = Path(tempfile.mkdtemp()).resolve()
    (root / "fake_agent.py").write_text(FAKE_AGENT)
    d = root / ".scratch" / "eff" / "issues"
    d.mkdir(parents=True)
    for name, head in tickets.items():
        (d / f"{name}.md").write_text(f"# Title {name}\n{head}\n")
    (root / ".gitignore").write_text(".scratch/\n_pm/\nseen.jsonl\nrunway.json\n")
    cmd = f"{sys.executable} {root / 'fake_agent.py'}"
    (root / "runway.json").write_text(json.dumps({
        "agent_cmd": cmd, "prep_cmd": cmd, "review_cmd": cmd, "check_cmd": check,
        "signin_cmds": {k: f"{sys.executable} -c pass" for k in ("claude", "codex", "gh")},  # never the real CLIs
        "worktree_dir": "../" + root.name + "-wt"}))
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def state(root):
    return json.loads((root / "_pm" / "runway-state.json").read_text())


class Heartbeat(unittest.TestCase):
    def drive(self, root, cfg_extra=None):
        """Run one in-process tick, capturing every state-file write."""
        cfg = dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()), **(cfg_extra or {}))
        os.environ["HB_ROOT"] = str(root)
        writes, orig = [], runway.write_state

        def spy(r, s):
            orig(r, s)
            writes.append(dict(s))
        runway.write_state = spy
        try:
            runway.tick(cfg, root, runway.make_tracker(cfg, root))
        finally:
            runway.write_state = orig
        return writes

    @staticmethod
    def phases(writes):
        out = []
        for w in writes:
            if not out or out[-1] != w["phase"]:
                out.append(w["phase"])
        return out

    def test_auto_ticket_phase_sequence(self):
        root = make_repo({"01-thing": ""})
        writes = self.drive(root)
        self.assertEqual(self.phases(writes), ["sync", "agent", "check", "merge"])
        last = state(root)
        self.assertEqual(last["version"], 1)
        self.assertEqual(last["ticket"], "eff/01")
        self.assertEqual(last["pid"], os.getpid())
        self.assertEqual(last["last_result"], "pass")
        self.assertRegex(last["since"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        self.assertRegex(last["tick_started"], r"^\d{4}-\d\d-\d\dT")
        self.assertIsNone(last["agent_pid"])

    def test_agent_sees_its_own_state_and_pid(self):
        root = make_repo({"01-thing": ""})
        self.drive(root)
        seen = json.loads((root / "seen.jsonl").read_text().splitlines()[0])
        self.assertEqual(seen["state"]["phase"], "agent")
        self.assertEqual(seen["state"]["attempt"], 1)
        self.assertEqual(seen["state"]["ticket"], "eff/01")
        self.assertEqual(seen["state"]["agent_pid"], seen["pid"])

    def test_failed_check_retries_then_parks(self):
        root = make_repo({"01-thing": ""}, check="false")
        writes = self.drive(root)
        self.assertEqual(self.phases(writes), ["sync", "agent", "check", "agent", "check"])
        self.assertEqual([w["attempt"] for w in writes if w["phase"] == "agent"][0:1], [1])
        self.assertEqual(max(w["attempt"] or 0 for w in writes), 2)
        self.assertIn("fail", [w["last_result"] for w in writes])
        self.assertEqual(state(root)["last_result"], "park")

    def test_prep_phase(self):
        root = make_repo({"01-ask": "Gate: human"})
        writes = self.drive(root)
        self.assertEqual(self.phases(writes), ["sync", "prep"])
        self.assertEqual(writes[-1]["ticket"], "eff/01")
        self.assertEqual(writes[-1]["agent_pid"], None)

    def test_writes_are_atomic(self):
        root = make_repo({"01-thing": ""})
        calls = []
        orig = os.replace
        os.replace = lambda a, b: (calls.append((a, b)), orig(a, b))[1]
        try:
            self.drive(root)
        finally:
            os.replace = orig
        target = str(root / "_pm" / "runway-state.json")
        calls = [(a, b) for a, b in calls if "runway-state" in str(b)]  # the sign-in file is atomic too
        self.assertTrue(calls and all(str(b) == target and str(a) != target for a, b in calls))
        self.assertEqual([p.name for p in (root / "_pm").glob("runway-state*")], ["runway-state.json"])

    def run_cli(self, root, *args, env=None):
        return subprocess.run([sys.executable, str(Path(runway.__file__)), "--root", str(root), *args],
                              capture_output=True, text=True, env={**os.environ, "HB_ROOT": str(root), **(env or {})})

    def test_loop_ends_idle(self):
        root = make_repo({"01-thing": ""})
        r = self.run_cli(root, "loop")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = state(root)
        self.assertEqual(s["phase"], "idle")
        self.assertEqual(s["last_result"], "pass")
        self.assertIsNone(s["ticket"])
        self.assertIsNone(s["agent_pid"])

    def test_crash_leaves_last_phase_with_dead_pid(self):
        root = make_repo({"01-thing": ""}, check="sh -c 'kill -9 $PPID'")
        r = self.run_cli(root, "tick")
        self.assertEqual(r.returncode, -9)
        s = state(root)
        self.assertEqual(s["phase"], "check")
        with self.assertRaises(ProcessLookupError):
            os.kill(s["pid"], 0)


if __name__ == "__main__":
    unittest.main()
