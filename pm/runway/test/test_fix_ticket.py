"""Offline tests: a failed review files a fix ticket back into the queue (gh-31). Markdown tracker on a real
repo, run_agent stubbed per call kind. Run: python3 -m pytest -q test_fix_ticket.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_heartbeat import make_repo  # noqa: E402

FAIL = json.dumps({"verdict": "fail", "blocking": ["x.py:3 off by one"], "non_blocking": ["nit"]})
PASS = json.dumps({"verdict": "pass", "blocking": [], "criteria": []})
TWO_WAY = "## Summary\nx\n## Evidence\ny\n## Merge danger\nTwo-way door.\n"
FINDINGS = "- Finding: x.py:3 off by one"


class FixTicket(unittest.TestCase):
    merge = "shadow"

    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = os.environ.get("RUNWAY_HOME")
        os.environ["RUNWAY_HOME"] = str(self.home)
        self.root = make_repo({"01-thing": "Status: resolved\n\n## Acceptance\n- it works"})
        self.cfg = dict(runway.DEFAULT_CONFIG, **json.loads((self.root / "runway.json").read_text()))
        self.cfg["merge"] = self.merge
        g = lambda *a: subprocess.run(["git", *a], cwd=self.root, check=True, capture_output=True)
        g("checkout", "-qb", "runway/integration")
        (self.root / "w.txt").write_text("x")
        g("add", "-A")
        g("commit", "-qm", "ticket work")
        g("checkout", "-q", "main")
        self.kinds, self.notes = [], []
        self.judge = FAIL
        self._orig = (runway.run_agent, runway.signin_waiting, runway.notify)
        runway.signin_waiting = lambda *a, **k: False
        runway.notify = lambda cfg, root, msg: self.notes.append(msg)
        runway.run_agent = self._agent
        self.tracker = runway.make_tracker(self.cfg, self.root)

    def tearDown(self):
        runway.run_agent, runway.signin_waiting, runway.notify = self._orig
        os.environ.pop("RUNWAY_HOME", None) if self._env is None else os.environ.__setitem__("RUNWAY_HOME", self._env)

    def _agent(self, cfg, root, cmd, cwd, prompt, ticket, kind, *a, **k):
        self.kinds.append(kind)
        m = re.search(r"head under review is ([0-9a-f]{40})", prompt)
        text = {"review": (f"Reviewed: {m.group(1)}\n" if m else "") + FINDINGS, "judge": self.judge, "pr": TWO_WAY}.get(kind, "")
        if kind == "judge":
            try:
                data = json.loads(text)
            except ValueError:
                data = {}
            if data.get("verdict") == "pass":
                expected = json.loads(prompt.split("Expected criterion inventory (cover each ticket/id exactly once):\n")[1].split("\n\nReview findings")[0])
                data["criteria"] = [dict(r, evidence="test_x passes") for r in expected]
                text = json.dumps(data)
        return SimpleNamespace(failure=None, returncode=0, auth=False, stderr=""), text

    def finish(self):
        self.assertTrue(runway.finish(self.cfg, self.root, self.tracker, force=True))

    def tickets(self):
        return runway.MarkdownTracker(self.root, self.cfg).load()

    def fixes(self):
        return [t for t in self.tickets() if t.title.startswith("Fix review findings")]

    def state(self):
        return json.loads((self.root / "_pm" / "runway-finish.json").read_text())

    def advance_head(self):
        wt = runway.integration_worktree(self.cfg, self.root)
        (wt / "more.txt").write_text(str(len(self.kinds)))
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
        subprocess.run(["git", "commit", "-qm", "fix work"], cwd=wt, check=True, capture_output=True)


class Shadow(FixTicket):
    def test_fail_files_one_ticket_and_runs_no_fix_pass(self):
        self.finish()
        self.assertNotIn("fix", self.kinds)
        fixes = self.fixes()
        self.assertEqual(len(fixes), 1)
        t = fixes[0]
        self.assertEqual(t.title, "Fix review findings on runway/integration (round 1)")
        self.assertIn("ready-for-agent", t.text)
        self.assertIn("x.py:3 off by one", t.text)
        self.assertEqual(self.state()["fix_ticket"], t.id)
        self.assertEqual(self.notes[-1], f"Review failed, fix ticket {t.id} filed")
        self.assertIn("Review: FAIL", (self.root / "_pm" / "runway-pr.md").read_text())

    def test_failing_check_output_goes_in_the_body(self):
        self.cfg["check_cmd"] = f"{sys.executable} -c \"import sys; print('boom-from-check'); sys.exit(1)\""
        self.finish()
        self.assertIn("boom-from-check", self.fixes()[0].text)

    def test_repeat_fail_on_same_head_comments_instead(self):
        self.finish()
        self.finish()
        self.assertEqual(len(self.fixes()), 1)
        self.assertIn("## Comments", self.fixes()[0].text)
        self.assertEqual(self.state()["round"], 1)

    def test_second_failed_round_parks_the_fix_ticket(self):
        self.finish()
        self.fixes()[0].mark_resolved("merged")
        self.advance_head()
        self.finish()
        self.assertEqual(len(self.fixes()), 1)
        parked = self.fixes()[0]
        self.assertEqual(parked.status, "needs-human")
        self.assertIn("x.py:3 off by one", parked.text)
        self.assertEqual(self.notes[-1], f"Review failed twice, {parked.id} parked for Joe")

    def test_new_batch_resets_the_count(self):
        self.finish()
        self.fixes()[0].mark_resolved("merged")
        d = self.root / ".scratch" / "eff" / "issues"
        (d / "09-new.md").write_text("# New thing\nStatus: resolved\n")
        self.advance_head()
        self.finish()
        self.assertEqual(len(self.fixes()), 2)
        self.assertEqual(self.state()["round"], 1)

    def test_pass_files_nothing(self):
        self.judge = PASS
        self.finish()
        self.assertEqual(self.fixes(), [])


class OnPass(Shadow):
    merge = "on_pass"


class Off(FixTicket):
    merge = "off"

    def test_off_keeps_the_fix_pass_and_files_nothing(self):
        self.finish()
        self.assertIn("fix", self.kinds)
        self.assertEqual(self.fixes(), [])


if __name__ == "__main__":
    unittest.main()
