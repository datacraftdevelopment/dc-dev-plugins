"""Offline tests for GitHub setup (setup.sh --github and `runway setup`) with a fake `gh`.
Run: python3 -m pytest -q test_github_setup.py"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNWAY_DIR = HERE.parent
sys.path.insert(0, str(RUNWAY_DIR))

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
data = json.load(open(os.environ["FAKE_GH_DATA"]))
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as f:
    f.write(json.dumps(args) + "\\n")
if args[:2] == ["auth", "status"]:
    if data.get("signed_out"):
        sys.stderr.write("You are not logged into any GitHub hosts. To log in, run: gh auth login")
        sys.exit(1)
    print("Logged in")
elif args[:2] == ["repo", "view"]:
    if data.get("no_repo"):
        sys.stderr.write("GraphQL: Could not resolve to a Repository with the name 'o/r'.")
        sys.exit(1)
    print(json.dumps({"hasIssuesEnabled": data.get("issues", True), "isPrivate": data.get("private", True)}))
elif args[:2] == ["label", "list"]:
    print(json.dumps([{"name": n, "color": "123456"} for n in data.get("labels", [])]))
elif args[:2] == ["label", "create"]:
    pass
else:
    sys.stderr.write("unexpected: %r" % (args,))
    sys.exit(2)
'''


class Fake:
    def __init__(self, **data):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.gh = d / "gh"
        self.gh.write_text(FAKE_GH)
        self.gh.chmod(self.gh.stat().st_mode | stat.S_IEXEC)
        self.data = d / "data.json"
        self.data.write_text(json.dumps(data))
        self.log = d / "log"
        self.log.write_text("")
        os.environ["FAKE_GH_DATA"] = str(self.data)
        os.environ["FAKE_GH_LOG"] = str(self.log)

    def calls(self):
        return [json.loads(x) for x in self.log.read_text().splitlines()]

    def creates(self):
        return [c for c in self.calls() if c[:2] == ["label", "create"]]


def tracker(fake):
    from github_tracker import GitHubTracker
    return GitHubTracker(Path("."), {"github": {"repo": "o/r", "gh": str(fake.gh)}})


class TrackerSetup(unittest.TestCase):
    def fake(self, **data):
        fake = Fake(**data)
        self.addCleanup(fake.tmp.cleanup)
        return fake

    def snippet(self, fake):
        return ("import sys; sys.path.insert(0, %r)\nfrom pathlib import Path\nfrom github_tracker import GitHubTracker\n"
                "GitHubTracker(Path('.'), {'github': {'repo': 'o/r', 'gh': %r}}).setup()" % (str(RUNWAY_DIR), str(fake.gh)))

    def test_creates_only_missing_labels_and_never_recolors(self):
        fake = self.fake(labels=["ready-for-agent", "go"], private=True)
        tracker(fake).setup()
        made = [c[2] for c in fake.creates()]
        self.assertEqual(sorted(made), ["needs-human", "ready-for-human"])
        self.assertFalse([c for c in fake.calls() if "--force" in c or c[:2] == ["label", "edit"]])
        self.assertTrue(all("--repo" in c and "o/r" in c for c in fake.creates()))

    def test_all_labels_present_creates_nothing(self):
        fake = self.fake(labels=["ready-for-agent", "ready-for-human", "go", "needs-human"])
        tracker(fake).setup()
        self.assertEqual(fake.creates(), [])

    def test_warns_when_public(self):
        fake = self.fake(private=False)
        out = subprocess.run([sys.executable, "-c", self.snippet(fake)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("PUBLIC", out.stdout)

    def test_private_has_no_public_warning(self):
        fake = self.fake(private=True)
        out = subprocess.run([sys.executable, "-c", self.snippet(fake)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("PUBLIC", out.stdout)

    def test_issues_disabled_stops_before_labels(self):
        fake = self.fake(issues=False)
        with self.assertRaises(SystemExit) as cm:
            tracker(fake).setup()
        self.assertIn("Issues", str(cm.exception))
        self.assertEqual(fake.creates(), [])

    def test_signed_out_stops_with_auth_help(self):
        fake = self.fake(signed_out=True)
        with self.assertRaises(SystemExit) as cm:
            tracker(fake).setup()
        self.assertIn("gh auth login", str(cm.exception))
        self.assertEqual(fake.creates(), [])

    def test_missing_repo_stops(self):
        fake = self.fake(no_repo=True)
        with self.assertRaises(SystemExit) as cm:
            tracker(fake).setup()
        self.assertIn("o/r", str(cm.exception))
        self.assertEqual(fake.creates(), [])

    def test_runway_setup_command_runs_github_setup(self):
        fake = self.fake(labels=[])
        root = Path(fake.tmp.name) / "repo"
        root.mkdir()
        (root / "runway.json").write_text(json.dumps({"tracker": "github", "github": {"repo": "o/r", "gh": str(fake.gh)}}))
        r = subprocess.run([sys.executable, str(RUNWAY_DIR / "runway.py"), "--root", str(root), "setup"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(fake.creates()), 4)


class SetupScript(unittest.TestCase):
    def sh(self, *args):
        return subprocess.run(["bash", str(RUNWAY_DIR / "setup.sh"), *args], capture_output=True, text=True,
                              env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                                       GIT_COMMITTER_EMAIL="t@t"))

    def test_github_mode_writes_doc_config_and_claude_md(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "proj"
            r = self.sh(str(repo), "--github", "acme/widgets")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            doc = (repo / "docs/agents/issue-tracker.md").read_text()
            self.assertIn("acme/widgets", doc)
            self.assertNotIn("{{", doc)
            self.assertIn("gh issue create", doc)         # Matt's conventions kept
            self.assertIn("ready-for-human", doc)         # Runway's labels
            self.assertIn("Never put both labels", doc)   # gating rule
            cfg = json.loads((repo / "runway.json").read_text())
            self.assertEqual(cfg["tracker"], "github")
            self.assertEqual(cfg["github"]["repo"], "acme/widgets")
            self.assertNotIn("linear", cfg)
            self.assertIn("GitHub", (repo / "CLAUDE.md").read_text())
            self.assertIn("runway.py", r.stdout)

    def test_github_mode_without_repo_arg_uses_origin(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "proj"
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:acme/gadgets.git"], check=True)
            (repo / "README.md").write_text("x")
            r = self.sh(str(repo), "--github")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads((repo / "runway.json").read_text())["github"]["repo"], "acme/gadgets")

    def test_github_mode_without_repo_or_origin_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.sh(str(Path(d) / "proj"), "--github")
            self.assertNotEqual(r.returncode, 0)

    def test_linear_mode_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "proj"
            r = self.sh(str(repo), "DAT", "Runway app")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            cfg = json.loads((repo / "runway.json").read_text())
            self.assertEqual(cfg["tracker"], "linear")
            self.assertEqual(cfg["linear"], {"team": "DAT", "project": "Runway app"})
            self.assertIn("Linear", (repo / "docs/agents/issue-tracker.md").read_text())


if __name__ == "__main__":
    unittest.main()
