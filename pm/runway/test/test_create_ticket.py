"""Offline tests: a tracker can open a new ticket (gh-28). GitHub is faked with a scripted `gh`, Linear at urlopen,
markdown on a temp folder. Run: python3 -m pytest -q test_create_ticket.py"""
import datetime as dt
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_tracker_down import FakeLinearAPI  # noqa: E402

MARK = "\U0001f6eb runway"

# `issue create` / `issue list` against data.json. Modes (one per call, from the modes file): ok,
# write-then-hang (the issue is created, gh never returns), hang (nothing happens, gh never returns).
FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys, time
argv = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as f:
    f.write(json.dumps(argv) + "\\n")
mf = os.environ["FAKE_GH_MODES"]
lines = open(mf).read().split() if os.path.exists(mf) else []
mode = lines.pop(0) if lines else "ok"
open(mf, "w").write(" ".join(lines))
path = os.environ["FAKE_GH_DATA"]
data = json.load(open(path))

def opt(name):
    return [argv[k + 1] for k, a in enumerate(argv) if a == name]

if argv[:2] == ["issue", "create"]:
    n = max([i["number"] for i in data["issues"]] + [0]) + 1
    if mode != "hang":
        data["issues"].append({"number": n, "title": opt("--title")[0], "body": opt("--body")[0],
                               "labels": opt("--label"), "repo": opt("--repo")[0],
                               "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        json.dump(data, open(path, "w"))
    if mode in ("hang", "write-then-hang"):
        time.sleep(30)
    print("https://github.com/o/r/issues/%d" % n)
elif argv[:2] == ["issue", "list"]:
    print(json.dumps(data["issues"]))
'''


class GitHubCreate(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()).resolve()
        gh = self.dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        for k, v in (("DATA", "data.json"), ("LOG", "log"), ("MODES", "modes")):
            os.environ[f"FAKE_GH_{k}"] = str(self.dir / v)
        (self.dir / "data.json").write_text(json.dumps({"issues": []}))
        self.cfg = {"tracker": "github", "github": {"repo": "o/r", "gh": str(gh), "timeout_s": 0.5}}
        self.tr = runway.make_tracker(self.cfg, self.dir)
        self.tr.c["park_authority"] = self.tr.park_owner()

    def stored(self):
        return json.loads((self.dir / "data.json").read_text())["issues"]

    def test_creates_in_the_configured_repo_with_labels_and_returns_the_ref(self):
        ref = self.tr.create("Fix the thing", "It broke.", ["ready-for-agent", "bug"])
        self.assertEqual(ref, "#1")
        (i,) = self.stored()
        self.assertEqual((i["repo"], i["title"], i["labels"]), ("o/r", "Fix the thing", ["ready-for-agent", "bug"]))

    def test_body_carries_the_runway_marker_so_it_is_not_joes(self):
        self.tr.create("t", "It broke.", [])
        self.assertEqual(self.stored()[0]["body"], MARK + " · It broke.")

    def test_a_create_that_landed_before_the_hang_is_not_made_twice(self):
        (self.dir / "modes").write_text("write-then-hang")
        ref = self.tr.create("t", "b", ["x"])
        self.assertEqual(len(self.stored()), 1)
        self.assertEqual(ref, "#1")

    def test_a_create_that_never_landed_is_made_on_retry(self):
        (self.dir / "modes").write_text("hang")
        ref = self.tr.create("t", "b", [])
        self.assertEqual((len(self.stored()), ref), (1, "#1"))

    def test_an_older_issue_with_the_same_title_is_not_mistaken_for_it(self):
        old = {"number": 7, "title": "t", "body": MARK + " · b", "labels": [], "createdAt": "2026-01-01T00:00:00Z"}
        (self.dir / "data.json").write_text(json.dumps({"issues": [old]}))
        (self.dir / "modes").write_text("hang")
        self.assertEqual(self.tr.create("t", "b", []), "#8")
        self.assertEqual(len(self.stored()), 2)


class LinearCreate(unittest.TestCase):
    def setUp(self):
        import linear_tracker as lt
        self.lt = lt
        self.api = FakeLinearAPI()
        self.created: list[dict] = []
        real = self.api.handle

        def handle(lt_, q, v):
            if q == lt.Q_PROJECTS:
                return {"projects": {"nodes": [{"id": "proj-1", "name": v["name"]}]}}
            if q == lt.M_CREATE:
                n = {"id": f"uuid-{len(self.created) + 1}", "identifier": f"DAT-{len(self.created) + 1}",
                     "title": v["input"]["title"], "description": v["input"]["description"],
                     "url": "https://linear.app/x/issue/DAT-1", "input": v["input"],
                     "createdAt": dt.datetime.now(dt.timezone.utc).isoformat()}
                self.created.append(n)
                return {"issueCreate": {"success": True, "issue": n}}
            if q == lt.Q_CREATED:
                return {"issues": {"nodes": list(self.created)}}
            if q == lt.Q_TEAM:
                d = real(lt_, q, v)
                d["teams"]["nodes"][0]["labels"]["nodes"] += [{"id": "l-bug", "name": "bug"}]
                return d
            return real(lt_, q, v)
        self.api.handle = handle
        p = mock.patch("urllib.request.urlopen", self.api)
        p.start()
        self.addCleanup(p.stop)
        cfg = {"tracker": "linear", "linear": {"team": "DAT", "project": "P"}}
        self.tr = runway.make_tracker(cfg, Path(tempfile.mkdtemp()))
        self.tr.c["park_authority"] = self.tr.park_owner()

    def test_creates_in_the_team_and_project_with_labels_and_returns_the_identifier(self):
        ref = self.tr.create("Fix it", "It broke.", ["bug"])
        self.assertEqual(ref, "DAT-1")
        inp = self.created[0]["input"]
        self.assertEqual((inp["teamId"], inp["projectId"], inp["labelIds"], inp["title"]),
                         ("t", "proj-1", ["l-bug"], "Fix it"))

    def test_description_carries_the_runway_marker(self):
        self.tr.create("t", "It broke.", [])
        self.assertEqual(self.created[0]["description"], MARK + " · It broke.")

    def test_a_create_that_landed_before_the_timeout_is_not_made_twice(self):
        self.api.faults[self.lt.M_CREATE] = ["timeout-after"]
        self.assertEqual(self.tr.create("t", "b", []), "DAT-1")
        self.assertEqual(len(self.created), 1)

    def test_a_create_that_never_landed_is_made_on_retry(self):
        self.api.faults[self.lt.M_CREATE] = ["timeout"]
        self.assertEqual(self.tr.create("t", "b", []), "DAT-1")
        self.assertEqual(len(self.created), 1)


class MarkdownCreate(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.issues = self.root / ".scratch" / "eff" / "issues"
        self.issues.mkdir(parents=True)
        (self.issues / "01-first.md").write_text("# First\n\nStatus: resolved\n")
        (self.issues / "02-second.md").write_text("# Second\n\nStatus: ready\n")
        self.tr = runway.make_tracker({"tracker": "markdown"}, self.root)

    def test_writes_the_next_numbered_file_and_returns_its_id(self):
        ref = self.tr.create("Fix the thing!", "It broke.", ["ready-for-agent"])
        self.assertEqual(ref, "eff/03")
        p = self.issues / "03-fix-the-thing.md"
        self.assertTrue(p.exists())
        t = runway.Ticket(p, self.root)
        self.assertEqual((t.title, t.status, t.id), ("Fix the thing!", "ready", "eff/03"))
        self.assertIn("It broke.", t.text)
        self.assertIn("ready-for-agent", t.text)

    def test_carries_the_runway_marker(self):
        self.tr.create("t", "It broke.", [])
        self.assertIn(MARK + " · ", (self.issues / "03-t.md").read_text())

    def test_the_created_ticket_loads_with_the_others(self):
        self.tr.create("t", "b", [])
        self.assertEqual([t.id for t in self.tr.load()], ["eff/01", "eff/02", "eff/03"])

    def test_with_several_efforts_one_must_be_named(self):
        (self.root / ".scratch" / "other" / "issues").mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.tr.create("t", "b", [])
        self.assertEqual(self.tr.create("t", "b", [], effort="other"), "other/01")


if __name__ == "__main__":
    unittest.main()
