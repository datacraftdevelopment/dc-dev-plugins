"""Offline tests: finish gives the round a pass/fail verdict. Run: python3 -m pytest -q test_verdict.py
Pure tests cover parsing and deciding; the finish tests stub run_agent per call kind and use a real repo."""
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

PASS = json.dumps({"verdict": "pass", "blocking": [], "non_blocking": ["nit"],
                   "criteria": [{"ticket": "eff/01", "criterion": "it works", "evidence": "test_x passes"}]})
TWO_WAY = "## Summary\nx\n## Evidence\ny\n## Merge danger\nTwo-way door. Revert the merge.\n"
ONE_WAY = "## Summary\nx\n## Evidence\ny\n## Merge danger\nOne-way door: drops a column.\n"


def tk(gate="auto", status="resolved"):
    return SimpleNamespace(gate=gate, status=status)


class Decide(unittest.TestCase):
    def test_check_failure_forces_fail_even_if_judge_says_pass(self):
        v = runway.decide_verdict(1, runway.parse_verdict(PASS))
        self.assertEqual(v["verdict"], "fail")
        self.assertIn("check failed", v["blocking"][0])

    def test_clean_and_green_passes(self):
        v = runway.decide_verdict(0, runway.parse_verdict("NO FINDINGS\n" + PASS))
        self.assertEqual(v["verdict"], "pass")
        self.assertEqual(v["blocking"], [])
        self.assertEqual(v["non_blocking"], ["nit"])

    def test_unparseable_judge_is_fail_never_pass(self):
        for text in ("", "looks good to me, pass", "{not json", '{"blocking": []}', None):
            v = runway.decide_verdict(0, runway.parse_verdict(text))
            self.assertEqual(v["verdict"], "fail", text)
            self.assertTrue(v["blocking"])

    def test_criterion_without_evidence_is_blocking(self):
        j = json.dumps({"verdict": "pass", "blocking": [],
                        "criteria": [{"ticket": "eff/01", "criterion": "docs updated", "evidence": ""}]})
        v = runway.decide_verdict(0, runway.parse_verdict(j))
        self.assertEqual(v["verdict"], "fail")
        self.assertIn("docs updated", v["blocking"][0])

    def test_judge_blocking_finding_fails(self):
        j = json.dumps({"verdict": "pass", "blocking": ["both seats: x.py:3 off by one"]})
        self.assertEqual(runway.decide_verdict(0, runway.parse_verdict(j))["verdict"], "fail")

    def test_judge_fail_verdict_fails(self):
        self.assertEqual(runway.decide_verdict(0, runway.parse_verdict('{"verdict": "fail"}'))["verdict"], "fail")

    def test_json_inside_prose_and_fences_parses(self):
        p = runway.parse_verdict("Here:\n```json\n" + PASS + "\n```\nDone.")
        self.assertEqual(p["verdict"], "pass")


class Hold(unittest.TestCase):
    def test_one_way_body_holds(self):
        self.assertTrue(runway.is_one_way(ONE_WAY, [tk()]))

    def test_two_way_body_with_auto_tickets_does_not_hold(self):
        self.assertFalse(runway.is_one_way(TWO_WAY, [tk()]))

    def test_needs_human_or_human_gate_holds(self):
        self.assertTrue(runway.is_one_way(TWO_WAY, [tk(), tk(status="needs-human")]))
        self.assertTrue(runway.is_one_way(TWO_WAY, [tk(gate="approved")]))

    def test_unassessed_merge_danger_holds(self):
        self.assertTrue(runway.is_one_way("## Summary\nx\n", [tk()]))


class Line(unittest.TestCase):
    def test_lines(self):
        fail = runway.decide_verdict(1, None)
        self.assertEqual(runway.verdict_line(fail, "off", False), "Review: FAIL, 2 blocking findings")
        ok = runway.decide_verdict(0, runway.parse_verdict(PASS))
        self.assertEqual(runway.verdict_line(ok, "shadow", False), "Review: PASS (would merge)")
        self.assertEqual(runway.verdict_line(ok, "off", False), "Review: PASS")
        self.assertIn("hold", runway.verdict_line(ok, "shadow", True))

    def test_default_merge_is_off(self):
        self.assertEqual(runway.DEFAULT_CONFIG["merge"], "off")


class FinishVerdict(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = os.environ.get("RUNWAY_HOME")
        os.environ["RUNWAY_HOME"] = str(self.home)
        self.root = make_repo({"01-thing": "Status: resolved\n\n## Acceptance\n- it works"})
        self.cfg = dict(runway.DEFAULT_CONFIG, **json.loads((self.root / "runway.json").read_text()))
        self.cfg["merge"] = "shadow"
        g = lambda *a: subprocess.run(["git", *a], cwd=self.root, check=True, capture_output=True)
        g("checkout", "-qb", "runway/integration")
        (self.root / "w.txt").write_text("x")
        g("add", "-A")
        g("commit", "-qm", "ticket work")
        g("checkout", "-q", "main")  # the worktree needs integ free
        self._orig = (runway.run_agent, runway.signin_waiting)
        runway.signin_waiting = lambda *a, **k: False
        self.judge_text = PASS
        self.pr_text = TWO_WAY
        runway.run_agent = self._agent

    def tearDown(self):
        runway.run_agent, runway.signin_waiting = self._orig
        os.environ.pop("RUNWAY_HOME", None) if self._env is None else os.environ.__setitem__("RUNWAY_HOME", self._env)

    def _agent(self, cfg, root, cmd, cwd, prompt, ticket, kind, *a, **k):
        m = re.search(r"head under review is ([0-9a-f]{40})", prompt)
        text = {"review": f"Reviewed: {m.group(1)}\nNO FINDINGS" if m else "NO FINDINGS", "judge": self.judge_text, "pr": self.pr_text}.get(kind, "")
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

    def finish(self, check="true"):
        self.cfg["check_cmd"] = check
        tracker = runway.make_tracker(self.cfg, self.root)
        self.assertTrue(runway.finish(self.cfg, self.root, tracker, force=True))
        recs = [json.loads(l) for l in (self.root / "_pm" / "runway-runs.jsonl").read_text().splitlines()]
        return [r for r in recs if r["kind"] == "verdict"], (self.root / "_pm" / "runway-pr.md").read_text()

    def test_green_check_and_clean_review_passes(self):
        rows, body = self.finish("true")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["verdict"], "pass")
        self.assertEqual(rows[0]["sha"], subprocess.run(["git", "rev-parse", "runway/integration"], cwd=self.root,
                                                        capture_output=True, text=True).stdout.strip())
        self.assertTrue(body.startswith(f"Review: PASS (would merge {rows[0]['sha']})"))
        review = (self.root / "_pm" / "runway-review.md").read_text()
        self.assertIn("Review: PASS", review)
        self.assertIn("test_x passes", review)

    def test_red_check_fails_the_round(self):
        rows, body = self.finish("false")
        self.assertEqual(rows[0]["verdict"], "fail")
        self.assertTrue(body.startswith("Review: FAIL, 1 blocking finding"))

    def test_garbage_judge_fails_the_round(self):
        self.judge_text = "I think it is fine."
        rows, body = self.finish("true")
        self.assertEqual(rows[0]["verdict"], "fail")
        self.assertTrue(body.startswith("Review: FAIL"))

    def test_one_way_body_marks_hold_but_can_pass(self):
        self.pr_text = ONE_WAY
        rows, body = self.finish("true")
        self.assertEqual(rows[0]["verdict"], "pass")
        self.assertTrue(rows[0]["hold"])
        self.assertIn("hold", body.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
