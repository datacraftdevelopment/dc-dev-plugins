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
        fake = self.fake(labels=["ready-for-agent", "go", "needs-triage", "needs-info", "wontfix"], private=True)
        tracker(fake).setup()
        made = [c[2] for c in fake.creates()]
        self.assertEqual(sorted(made), ["needs-human", "ready-for-human", "spec"])
        self.assertFalse([c for c in fake.calls() if "--force" in c or c[:2] == ["label", "edit"]])
        self.assertTrue(all("--repo" in c and "o/r" in c for c in fake.creates()))

    def test_all_labels_present_creates_nothing(self):
        fake = self.fake(labels=["ready-for-agent", "ready-for-human", "go", "needs-human", "spec",
                                 "needs-triage", "needs-info", "wontfix"])
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
        self.assertEqual(len(fake.creates()), 8)   # Runway's five plus needs-triage, needs-info, wontfix

    def test_creates_matts_five_triage_labels_when_missing(self):
        fake = self.fake(labels=[])
        tracker(fake).setup()
        made = {c[2] for c in fake.creates()}
        self.assertTrue({"needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix"} <= made)

    def test_existing_matt_labels_are_left_alone(self):
        fake = self.fake(labels=["Needs-Triage", "needs-info", "wontfix", "ready-for-agent", "ready-for-human",
                                 "go", "needs-human", "spec"])
        tracker(fake).setup()
        self.assertEqual(fake.creates(), [])


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

    BLOCK_HEADS = ("## Agent skills", "### Issue tracker", "### Triage labels", "### Domain docs")
    ARGS = {"github": ("--github", "acme/widgets"), "linear": ("DAT", "Runway app")}

    def check_matt_files(self, repo):
        for head in self.BLOCK_HEADS:
            self.assertIn(head, (repo / "CLAUDE.md").read_text())
        labels = (repo / "docs/agents/triage-labels.md").read_text()
        for word in ("needs-triage", "needs-info", "wontfix", "`go`", "`needs-human`", "`spec`", "Joe decides"):
            self.assertIn(word, labels)
        self.assertIn("GLOSSARY.md", (repo / "docs/agents/domain.md").read_text())

    def test_both_trackers_write_all_three_docs_and_full_block(self):
        for mode, args in self.ARGS.items():
            with self.subTest(mode), tempfile.TemporaryDirectory() as d:
                repo = Path(d) / "proj"
                self.assertEqual(self.sh(str(repo), *args).returncode, 0)
                self.check_matt_files(repo)

    def test_existing_docs_and_block_are_never_overwritten(self):
        for mode, args in self.ARGS.items():
            with self.subTest(mode), tempfile.TemporaryDirectory() as d:
                repo = Path(d) / "proj"
                self.assertEqual(self.sh(str(repo), *args).returncode, 0)
                (repo / "docs/agents/triage-labels.md").write_text("MINE labels\n")
                (repo / "docs/agents/domain.md").write_text("MINE domain\n")
                (repo / "CLAUDE.md").write_text("# x\n\n## Agent skills\n\nMINE block\n")
                r = self.sh(str(repo), *args)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual((repo / "docs/agents/triage-labels.md").read_text(), "MINE labels\n")
                self.assertEqual((repo / "docs/agents/domain.md").read_text(), "MINE domain\n")
                self.assertEqual((repo / "CLAUDE.md").read_text(), "# x\n\n## Agent skills\n\nMINE block\n")

    def test_rerun_restores_gating_rule_after_matts_setup(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "proj"
            self.sh(str(repo), *self.ARGS["github"])
            (repo / "docs/agents/issue-tracker.md").write_text("plain Matt doc\n")
            self.sh(str(repo), *self.ARGS["github"])
            self.assertIn("Never put both labels", (repo / "docs/agents/issue-tracker.md").read_text())

    def test_rerun_commits_only_files_it_owns(self):
        for mode, args in self.ARGS.items():
            with self.subTest(mode), tempfile.TemporaryDirectory() as d:
                repo = Path(d) / "proj"
                self.assertEqual(self.sh(str(repo), *args).returncode, 0)
                git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,
                                                check=True).stdout
                (repo / "docs/agents/worker-env.md").write_text("committed\n")
                (repo / "docs/agents/issue-tracker.md").write_text("plain doc\n")   # setup restores it, so it commits
                git("add", "docs/agents/worker-env.md", "docs/agents/issue-tracker.md")
                git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "worker env")
                (repo / "docs/agents/worker-env.md").write_text("dirty edit\n")
                (repo / "docs/agents/notes.md").write_text("untracked\n")
                (repo / "docs/agents/triage-labels.md").write_text("MINE labels\n")
                r = self.sh(str(repo), *args)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(git("show", "--name-only", "--format=", "HEAD").split(), ["docs/agents/issue-tracker.md"])
                status = git("status", "--porcelain")
                for path in ("worker-env.md", "notes.md", "triage-labels.md"):
                    self.assertIn(path, status)

    def test_fresh_repo_commits_all_three_docs(self):
        for mode, args in self.ARGS.items():
            with self.subTest(mode), tempfile.TemporaryDirectory() as d:
                repo = Path(d) / "proj"
                self.assertEqual(self.sh(str(repo), *args).returncode, 0)
                files = subprocess.run(["git", "-C", str(repo), "show", "--name-only", "--format=", "HEAD"],
                                       capture_output=True, text=True, check=True).stdout.split()
                self.assertEqual(sorted(files), ["CLAUDE.md", "docs/agents/domain.md", "docs/agents/issue-tracker.md",
                                                 "docs/agents/triage-labels.md", "runway.json"])

    def test_linear_mode_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "proj"
            r = self.sh(str(repo), "DAT", "Runway app")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            cfg = json.loads((repo / "runway.json").read_text())
            self.assertEqual(cfg["tracker"], "linear")
            self.assertEqual(cfg["linear"], {"park_authority": "", "team": "DAT", "project": "Runway app"})
            self.assertIn("Linear", (repo / "docs/agents/issue-tracker.md").read_text())


if __name__ == "__main__":
    unittest.main()
