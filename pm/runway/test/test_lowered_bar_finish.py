"""Offline tests: the lowered-bar scan inside finish() (gh-91). Real git, run_agent stubbed.
Run: python3 -m pytest -q test_lowered_bar_finish.py"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lowered_bar  # noqa: E402
import runway  # noqa: E402
from test_fix_ticket import FixTicket, PASS  # noqa: E402

HIT_ID = "LB:new-suppression:a.py:1"


def inventory(prompt):
    """The expected criterion inventory the judge prompt carries."""
    return json.loads(prompt.split("Expected criterion inventory (cover each ticket/id exactly once):\n")[1]
                      .split("\n\nReview findings")[0])


class Base(FixTicket):
    merge = "shadow"
    judge_edit = None

    def setUp(self):
        super().setUp()
        self.judge = PASS
        self.judge_prompts = []
        self.commit_a("x = 1  # no" + "qa\n")

    def commit_a(self, text):
        wt = runway.integration_worktree(self.cfg, self.root)
        runway.reset_worktree(wt)
        (wt / "a.py").write_text(text)
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
        subprocess.run(["git", "commit", "-qm", "edit a"], cwd=wt, check=True, capture_output=True)

    def _agent(self, cfg, root, cmd, cwd, prompt, ticket, kind, *a, **k):
        if kind == "judge":
            self.judge_prompts.append(prompt)
        r, text = super()._agent(cfg, root, cmd, cwd, prompt, ticket, kind, *a, **k)
        if kind == "judge" and self.judge_edit:
            edit = self.judge_edit(inventory(prompt)) if callable(self.judge_edit) else self.judge_edit
            text = json.dumps({**json.loads(text), **edit})
        return r, text

    def last_verdict(self):
        rows = [json.loads(x) for x in (self.root / "_pm" / "runway-runs.jsonl").read_text().splitlines()]
        return [r for r in rows if r["kind"] == "verdict"][-1]


class InFinish(Base):
    def test_hit_reaches_the_judge_and_fails_a_judge_pass(self):
        self.finish()
        self.assertIn("lowered-bar scan", self.judge_prompts[0])
        self.assertIn(HIT_ID, self.judge_prompts[0])
        v = self.last_verdict()
        self.assertEqual(v["verdict"], "fail")
        self.assertTrue(any(HIT_ID in b for b in v["blocking"]), v["blocking"])

    def test_ticket_quote_clears_it(self):
        self.judge_edit = lambda inv: {"cleared": [{"id": HIT_ID, "ticket": inv[0]["ticket"], "criterion": inv[0]["id"],
                                                    "quote": "it works"}]}
        self.finish()
        v = self.last_verdict()
        self.assertEqual(v["verdict"], "pass")
        self.assertTrue(any(HIT_ID in n and "Cleared" in n for n in v["non_blocking"]), v["non_blocking"])

    def test_quote_with_no_criterion_id_does_not_clear_it(self):
        self.judge_edit = {"cleared": [{"id": HIT_ID, "quote": "it works"}]}
        self.finish()
        self.assertEqual(self.last_verdict()["verdict"], "fail")

    def test_invented_quote_does_not_clear_it(self):
        self.judge_edit = {"cleared": [{"id": HIT_ID, "quote": "looks fine to me, honestly"}]}
        self.finish()
        self.assertEqual(self.last_verdict()["verdict"], "fail")

    def test_scan_that_cannot_run_blocks_even_when_the_judge_passes(self):
        orig = lowered_bar.scan
        lowered_bar.scan = lambda *a, **k: [{"rule": "scan-error", "file": "", "line": 0, "hunk": "git broke"}]
        self.addCleanup(setattr, lowered_bar, "scan", orig)
        self.judge_edit = {"cleared": [{"id": "LB:scan-error::0", "quote": "it works"}]}
        self.finish()
        self.assertEqual(self.last_verdict()["verdict"], "fail")

    def test_hits_show_in_the_pr_body_in_shadow(self):
        self.finish()
        self.assertIn(HIT_ID, (self.root / "_pm" / "runway-pr.md").read_text())

    def test_clean_diff_adds_no_blocking(self):
        self.commit_a("x = 1\n")
        self.finish()
        self.assertEqual(self.last_verdict()["verdict"], "pass")


class MergeOff(Base):
    merge = "off"

    def test_hits_still_appear_in_the_pr_body(self):
        self.finish()
        self.assertIn(HIT_ID, (self.root / "_pm" / "runway-pr.md").read_text())
        self.assertEqual(self.last_verdict()["verdict"], "fail")


if __name__ == "__main__":
    unittest.main()
