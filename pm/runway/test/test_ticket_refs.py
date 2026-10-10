"""Offline tests: ticket refs in Runway's commit messages and the PR body.
Run: python3 -m pytest -q test_ticket_refs.py"""
import json
import os
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


def git(root, *a):
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def gh_ticket(n=12):
    return SimpleNamespace(effort="github", id="#" + str(n), ref="https://github.com/o/r/issues/" + str(n), title="T",
                           commit_ref="#" + str(n), pr_ref="Refs #" + str(n))


def lin_ticket(ident="DAT-41"):
    return SimpleNamespace(effort="linear", id=ident, ref="https://linear.app/x/issue/" + ident + "/t", title="T",
                           commit_ref=ident, pr_ref="Refs https://linear.app/x/issue/" + ident + "/t")


def local_ticket():
    return SimpleNamespace(effort="eff", id="eff/01", ref=".scratch/eff/issues/01-a.md", title="T",
                           commit_ref="", pr_ref="")


class Refs(unittest.TestCase):
    def test_commit_ref(self):
        self.assertEqual(runway.commit_ref(gh_ticket()), "(#12)")
        self.assertEqual(runway.commit_ref(lin_ticket()), "(DAT-41)")
        self.assertEqual(runway.commit_ref(local_ticket()), "")

    def test_auto_commit_message(self):
        self.assertEqual(runway.auto_commit_msg(gh_ticket()), "runway: T (#12) (auto-commit)")
        self.assertEqual(runway.auto_commit_msg(local_ticket()), "runway: T (auto-commit)")

    def test_refs_block(self):
        b = runway.refs_block([gh_ticket(12), gh_ticket(13), lin_ticket(), local_ticket()])
        self.assertIn("Refs #12", b)
        self.assertIn("Refs #13", b)
        self.assertIn("https://linear.app/x/issue/DAT-41/t", b)
        self.assertNotRegex(b.lower(), r"closes|fixes|resolves")
        self.assertEqual(runway.refs_block([local_ticket()]), "")


class RealTickets(unittest.TestCase):
    """The refs the real ticket classes give, not fakes."""

    def test_markdown_ticket_has_no_refs(self):
        root = make_repo({"01-thing": "Status: ready"})
        t = runway.make_tracker({"tracker": "markdown"}, root).load()[0]
        self.assertEqual((t.commit_ref, t.pr_ref), ("", ""))

    def test_github_ticket(self):
        from test_github_tracker import issue
        from github_tracker import GitHubTicket
        gh = runway.make_tracker({"tracker": "github", "github": {"repo": "o/r"}}, Path(tempfile.mkdtemp()))
        t = GitHubTicket(issue(12), gh)
        self.assertEqual((t.commit_ref, t.pr_ref), ("#12", "Refs #12"))

    def test_linear_ticket(self):
        from test_linear_spec import node
        import linear_tracker
        tr = type("Tr", (), {"c": dict(linear_tracker.DEFAULTS, team="DAT")})()
        t = linear_tracker.LinearTicket(node(41), tr)
        self.assertEqual((t.commit_ref, t.pr_ref), ("DAT-41", "Refs https://linear.app/x/issue/DAT-41"))


class Merge(unittest.TestCase):
    def merged_subject(self, ticket):
        os.environ["RUNWAY_HOME"] = str(Path(tempfile.mkdtemp()).resolve())
        root = make_repo({"01-thing": "Status: ready"})
        cfg = dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))
        git(root, "branch", cfg["integration_branch"])
        git(root, "checkout", "-qb", "runway/t")
        (root / "w.txt").write_text("x")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "work")
        git(root, "checkout", "-q", "main")
        self.assertTrue(runway.merge_into_integration(cfg, root, "runway/t", runway.commit_ref(ticket)))
        return git(root, "log", "-1", "--format=%s", cfg["integration_branch"])

    def test_github(self):
        self.assertEqual(self.merged_subject(gh_ticket()), "runway: merge runway/t (#12)")

    def test_linear(self):
        self.assertEqual(self.merged_subject(lin_ticket()), "runway: merge runway/t (DAT-41)")

    def test_local(self):
        self.assertEqual(self.merged_subject(local_ticket()), "runway: merge runway/t")


if __name__ == "__main__":
    unittest.main()
