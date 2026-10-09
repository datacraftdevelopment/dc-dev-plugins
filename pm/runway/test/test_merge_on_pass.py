"""Offline tests: merge: on_pass merges the reviewed commit (gh-32). Real git with a bare origin, gh faked,
run_agent stubbed. Run: python3 -m pytest -q test_merge_on_pass.py"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_fix_ticket import FixTicket, PASS, TWO_WAY  # noqa: E402

ONE_WAY = "## Summary\nx\n## Evidence\ny\n## Merge danger\nOne-way door.\n"
URL = "https://github.com/o/r/pull/1"


class Merge:
    """Shared setup; the test classes below mix it into FixTicket (the unittest base is applied once, below)."""
    merge = "on_pass"
    pr = "draft"
    pr_body = TWO_WAY

    def setUp(self):
        super().setUp()
        self.judge = PASS
        self.cfg["pr"] = self.pr
        self.gh = []
        self.gh_fail = None
        self.origin = Path(self.root.parent / (self.root.name + "-origin.git"))
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True)
        self.g("remote", "add", "origin", str(self.origin))
        self.g("push", "-q", "origin", "main")
        self._sh, self._pr = runway.sh, runway.open_draft_pr
        runway.sh = self._fake_sh
        runway.open_draft_pr = lambda *a, **k: URL
        self.addCleanup(self._restore)

    def _restore(self):
        runway.sh, runway.open_draft_pr = self._sh, self._pr

    def g(self, *a):
        return subprocess.run(["git", *a], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def _fake_sh(self, cmd, cwd, *a, **k):
        if cmd[0] == "gh":
            self.gh.append(cmd)
            bad = self.gh_fail and cmd[2] == self.gh_fail
            return subprocess.CompletedProcess(cmd, 1 if bad else 0, "", "refused" if bad else "")
        return self._sh(cmd, cwd, *a, **k)

    def _agent(self, cfg, root, cmd, cwd, prompt, ticket, kind, *a, **k):
        r, text = super()._agent(cfg, root, cmd, cwd, prompt, ticket, kind, *a, **k)
        return r, (self.pr_body if kind == "pr" else text)

    def merges(self):
        p = self.root / "_pm" / "runway-runs.jsonl"
        return [r for r in map(json.loads, p.read_text().splitlines()) if r["kind"] == "merge"]

    def reviewed(self):
        return self.g("rev-parse", "runway/integration")


class DraftMerge(Merge, FixTicket):
    def test_pass_merges_at_the_reviewed_sha(self):
        self.finish()
        sha = self.reviewed()
        self.assertEqual(self.gh, [["gh", "pr", "ready", "runway/integration"],
                                   ["gh", "pr", "merge", "runway/integration", "--merge",
                                    "--match-head-commit", sha]])
        self.assertEqual(self.merges()[0]["sha"], sha)
        self.assertEqual(self.merges()[0]["pr"], URL)
        self.assertEqual(self.notes[-1], "Merged 1 tickets into main")

    def test_gh_refusing_a_moved_head_does_not_merge(self):
        self.gh_fail = "merge"
        self.finish()
        self.assertEqual(self.merges(), [])
        self.assertNotIn("Merged", self.notes[-1])

    def test_head_moved_since_review_never_calls_gh(self):
        sha = self.reviewed()
        orig = runway.merge_reviewed

        def moved(cfg, root, reviewed, pr_url):  # the head moves between the review and the merge
            self.g("update-ref", "refs/heads/runway/integration", self.g("rev-parse", "main"))
            return orig(cfg, root, reviewed, pr_url)
        runway.merge_reviewed = moved
        self.addCleanup(lambda: setattr(runway, "merge_reviewed", orig))
        self.finish()
        self.assertNotEqual(self.reviewed(), sha)
        self.assertEqual(self.gh, [])
        self.assertEqual(self.merges(), [])

    def test_hold_never_merges_and_says_why(self):
        self.pr_body = ONE_WAY
        self.finish()
        self.assertEqual(self.gh, [])
        self.assertEqual(self.merges(), [])
        self.assertIn("Held for Joe: one-way door", (self.root / "_pm" / "runway-pr.md").read_text())

    def test_fail_never_merges(self):
        self.judge = json.dumps({"verdict": "fail", "blocking": ["x"], "non_blocking": []})
        self.finish()
        self.assertEqual(self.gh, [])


class ShadowNeverMerges(Merge, FixTicket):
    merge = "shadow"

    def test_shadow_writes_would_merge_sha_and_does_nothing(self):
        self.finish()
        self.assertEqual(self.gh, [])
        self.assertEqual(self.merges(), [])
        self.assertIn(f"would merge {self.reviewed()}", (self.root / "_pm" / "runway-pr.md").read_text())
        self.assertEqual(self.g("rev-parse", "main"), self.g("rev-parse", "origin/main"))
        self.assertNotIn("Merged", self.notes[-1])


class FileMerge(Merge, FixTicket):
    pr = "file"

    def test_pass_merges_locally_and_pushes_the_reviewed_sha(self):
        self.finish()
        sha = self.reviewed()
        self.g("fetch", "-q", "origin")
        self.assertEqual(self.g("rev-parse", "origin/main^2"), sha)
        self.assertEqual(self.gh, [])
        self.assertEqual(self.merges()[0]["sha"], sha)
        self.assertEqual(self.notes[-1], "Merged 1 tickets into main")

    def test_conflict_aborts_and_logs(self):
        (self.root / "w.txt").write_text("different")
        self.g("add", "-A")
        self.g("commit", "-qm", "base change")
        self.g("push", "-q", "origin", "main")
        before = self.g("rev-parse", "origin/main")
        self.finish()
        self.assertEqual(self.merges(), [])
        self.g("fetch", "-q", "origin")
        self.assertEqual(self.g("rev-parse", "origin/main"), before)

    def test_hold_never_merges(self):
        self.pr_body = ONE_WAY
        self.finish()
        self.assertEqual(self.merges(), [])


if __name__ == "__main__":
    unittest.main()
