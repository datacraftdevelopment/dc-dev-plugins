"""Offline tests for the GitHub tracker's write side with a stateful fake `gh`: claim, resolve, park, release,
other-Mac claims, and one tick taking an issue from ready to closed. Run: python3 -m pytest -q test_github_write.py"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_github_tracker import issue  # noqa: E402
from test_heartbeat import make_repo  # noqa: E402

CLAIM = "\U0001f6eb runway · Claimed-by: {} · Started on `b`."

# Reads answer from data.json; `issue edit / comment / close` change it, like GitHub would.
FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
path = os.environ["FAKE_GH_DATA"]
data = json.load(open(path))
argv = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as f:
    f.write(json.dumps(argv) + "\\n")
issues = {i["number"]: i for i in data["issues"]}

def opt(name):
    return [argv[k + 1] for k, a in enumerate(argv) if a == name]

if argv[0] == "api":
    q = next(a[6:] for a in argv if a.startswith("query="))
    if "issues(first" in q:
        nodes = [i for i in data["issues"] if any(l["name"] in ("ready-for-agent", "ready-for-human") for l in i["labels"]["nodes"])]
        print(json.dumps({"data": {"repository": {"issues": {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": ""}}}}}))
    else:
        n = int(next(a[7:] for a in argv if a.startswith("number=")))
        print(json.dumps({"data": {"repository": {"issue": issues[n]}}}))
    sys.exit(0)

verb, n = argv[1], int(argv[2])
i = issues[n]
if "--add-assignee" in argv:
    i["assignees"] = {"totalCount": 1, "nodes": [{"login": "joe"}]}
if "--remove-assignee" in argv:
    i["assignees"] = {"totalCount": 0, "nodes": []}
for name in opt("--add-label"):
    i["labels"]["nodes"].append({"name": name})
for name in opt("--remove-label"):
    i["labels"]["nodes"] = [l for l in i["labels"]["nodes"] if l["name"] != name]
body = (opt("--body") or opt("--comment") or [None])[0]
if body:
    k = len(i["comments"]["nodes"]) + 1
    i["comments"]["nodes"].append({"body": body, "createdAt": "2026-10-09T10:%02d:00Z" % k, "authorAssociation": "OWNER"})
if verb == "close":
    i["state"], i["stateReason"] = "CLOSED", opt("--reason")[0].upper().replace(" ", "_")
json.dump(data, open(path, "w"))
'''


class GitHubWrites(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()).resolve()
        gh = self.dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        os.environ["FAKE_GH_DATA"] = str(self.dir / "data.json")
        os.environ["FAKE_GH_LOG"] = str(self.dir / "log")
        self.cfg = {"tracker": "github", "github": {"repo": "o/r", "gh": str(gh)}}

    def data(self, *issues):
        (self.dir / "data.json").write_text(json.dumps({"issues": list(issues)}))

    def stored(self, n=1):
        return next(i for i in json.loads((self.dir / "data.json").read_text())["issues"] if i["number"] == n)

    def tracker(self):
        return runway.make_tracker(self.cfg, self.dir)

    def ticket(self, n=1):
        return next(t for t in self.tracker().load() if t.id == f"#{n}")

    def comments(self, n=1):
        return [c["body"] for c in self.stored(n)["comments"]["nodes"]]

    # -- the four writes --

    def test_claim_assigns_and_comments_machine_and_branch(self):
        self.data(issue(1))
        self.ticket().mark_claimed("runway/github-gh-1-issue-1", "Mini-One")
        self.assertEqual(self.stored()["assignees"]["totalCount"], 1)
        self.assertEqual(self.comments(), ["\U0001f6eb runway · Claimed-by: Mini-One · Started on `runway/github-gh-1-issue-1`."])
        t = self.ticket()
        self.assertEqual((t.status, t.claimed_by), ("claimed", "Mini-One"))
        call = next(json.loads(l) for l in (self.dir / "log").read_text().splitlines() if "--add-assignee" in l)
        self.assertEqual(call[call.index("--add-assignee") + 1], "@me")
        self.assertEqual(call[call.index("--repo") + 1], "o/r")

    def test_resolve_closes_as_completed_with_the_note(self):
        self.data(issue(1, assignees=1))
        self.ticket().mark_resolved("Done on `b`, check passed.")
        s = self.stored()
        self.assertEqual((s["state"], s["stateReason"]), ("CLOSED", "COMPLETED"))
        self.assertEqual(self.comments(), ["\U0001f6eb runway · Done on `b`, check passed."])
        self.assertEqual(self.ticket().status, "resolved")

    def test_park_labels_unassigns_and_says_why_then_label_removal_makes_it_ready(self):
        self.data(issue(1))
        self.ticket().mark_claimed("b", "Mini-One")
        self.ticket().mark_needs_human("run failed", "Check failed.")
        t = self.ticket()
        self.assertEqual((t.status, t.claimed_by), ("needs-human", None))
        self.assertEqual(self.stored()["assignees"]["totalCount"], 0)
        self.assertIn("Parked: run failed. Remove `needs-human` or comment `go` to retry.\n\nCheck failed.", self.comments()[-1])
        self.assertEqual(t.packet.splitlines()[0], "Parked: run failed. Remove `needs-human` or comment `go` to retry.")
        s = self.stored()  # Joe removes the label
        s["labels"]["nodes"] = [l for l in s["labels"]["nodes"] if l["name"] != "needs-human"]
        self.data(s)
        self.assertEqual(self.ticket().status, "ready")

    def test_release_unassigns_and_the_claim_clears(self):
        self.data(issue(1))
        self.ticket().mark_claimed("b", "Mini-One")
        self.ticket().mark_ready("stopped by pause")
        t = self.ticket()
        self.assertEqual((t.status, t.claimed_by), ("ready", None))
        self.assertEqual(self.stored()["assignees"]["totalCount"], 0)
        self.assertEqual(self.comments()[-1], "\U0001f6eb runway · stopped by pause")

    def test_unassign_names_the_login_the_issue_reports(self):
        self.data(issue(1))
        s = self.stored()
        s["assignees"] = {"totalCount": 1, "nodes": [{"login": "joe"}]}
        self.data(s)
        self.ticket().mark_ready("x")
        call = next(json.loads(l) for l in (self.dir / "log").read_text().splitlines() if "--remove-assignee" in l)
        self.assertEqual(call[call.index("--remove-assignee") + 1], "joe")

    def test_write_failure_is_an_error_not_silence(self):
        self.data(issue(1))
        t = self.ticket()
        os.environ["FAKE_GH_DATA"] = str(self.dir / "missing.json")
        with self.assertRaises(Exception):
            t.mark_claimed("b", "Mini-One")

    # -- an approved ticket that parks waits for a fresh go (gh-13) --

    def park_approved(self):
        self.data(issue(1, labels=("ready-for-human", "go")))
        self.ticket().mark_claimed("b", "Mini-One")
        self.ticket().mark_needs_human("checks failed", "boom")

    def labels(self):
        return [lb["name"] for lb in self.stored()["labels"]["nodes"]]

    def test_park_of_an_approved_ticket_drops_go_and_says_to_comment_go(self):
        self.park_approved()
        self.assertIn("needs-human", self.labels())
        self.assertNotIn("go", self.labels())
        self.assertIn("Parked: checks failed. Comment `go` (or re-add the `go` label) to retry.", self.comments()[-1])

    def test_park_then_sync_leaves_it_parked_across_ticks(self):
        self.park_approved()
        for _ in range(3):
            self.tracker().sync()
            self.assertEqual(self.ticket().status, "needs-human")
        self.assertEqual(self.tick_as("Mini-Two")[0], [])
        self.assertEqual(len(self.comments()), 2)  # claim + park: no "Approved." churn

    def test_park_then_go_comment_approves_and_retries(self):
        self.park_approved()
        s = self.stored()
        s["comments"]["nodes"].append({"body": "go", "createdAt": "2026-10-10T10:00:00Z", "authorAssociation": "OWNER"})
        self.data(s)
        self.tracker().sync()
        self.assertEqual(self.tick_as("Mini-Two")[0], ["#1"])

    def test_park_then_go_label_readded_approves_and_retries(self):
        self.park_approved()
        s = self.stored()
        s["labels"]["nodes"].append({"name": "go"})
        self.data(s)
        self.tracker().sync()
        self.assertEqual(self.tick_as("Mini-Two")[0], ["#1"])

    def test_a_go_comment_from_before_the_park_does_not_count(self):
        self.data(issue(1, labels=("ready-for-human", "go"), comments=[("go", "OWNER")]))
        self.ticket().mark_claimed("b", "Mini-One")
        self.ticket().mark_needs_human("checks failed", "boom")
        self.tracker().sync()
        self.assertEqual(self.ticket().status, "needs-human")

    def test_a_parked_ready_for_agent_ticket_is_ready_when_the_label_goes(self):
        self.data(issue(1))
        self.ticket().mark_claimed("b", "Mini-One")
        self.ticket().mark_needs_human("x", "d")
        self.tracker().sync()
        self.assertEqual(self.ticket().status, "needs-human")
        s = self.stored()
        s["labels"]["nodes"] = [lb for lb in s["labels"]["nodes"] if lb["name"] != "needs-human"]
        self.data(s)
        self.assertEqual(self.tick_as("Mini-Two")[0], ["#1"])

    def test_release_keeps_go_so_the_approved_ticket_runs_again(self):
        self.data(issue(1, labels=("ready-for-human", "go")))
        self.ticket().mark_claimed("b", "Mini-One")
        self.ticket().mark_ready("stopped by pause")
        self.assertIn("go", self.labels())
        self.assertEqual(self.tick_as("Mini-Two")[0], ["#1"])

    # -- claims between Macs (mirrors the Linear claim tests) --

    def tick_as(self, me):
        ran, lg = [], mock.MagicMock()
        with mock.patch.object(runway, "machine_name", return_value=me), \
                mock.patch.object(runway, "run_ticket", side_effect=lambda cfg, r, tr, t: ran.append(t.id)), \
                mock.patch.object(runway, "sync_base", return_value=True), \
                mock.patch.object(runway, "signin_waiting_for_work", return_value=False), \
                mock.patch.object(runway, "log", lg):
            runway.tick(dict(runway.DEFAULT_CONFIG), self.dir, self.tracker())
        return ran, [c.args[1] for c in lg.call_args_list]

    def test_another_macs_claim_is_skipped_and_logged(self):
        self.data(issue(1, assignees=1, comments=[(CLAIM.format("Mini-One"), "OWNER")]))
        ran, logs = self.tick_as("Mini-Two")
        self.assertEqual(ran, [])
        self.assertIn("skip #1 claimed by Mini-One", logs)

    def test_pause_stop_then_other_mac_takes_it(self):
        self.data(issue(1))
        self.ticket().mark_claimed("b", "Mini-One")
        self.assertEqual(self.tick_as("Mini-Two")[0], [])
        self.ticket().mark_ready("stopped by pause")
        ran, logs = self.tick_as("Mini-Two")
        self.assertEqual(ran, ["#1"])
        self.assertFalse([l for l in logs if "claimed by" in l])

    def test_park_then_retry_on_another_mac(self):
        self.data(issue(1))
        self.ticket().mark_claimed("b", "Mini-One")
        self.ticket().mark_needs_human("x", "d")
        self.assertEqual(self.tick_as("Mini-Two")[0], [])  # parked: nobody runs it
        s = self.stored()
        s["labels"]["nodes"] = [l for l in s["labels"]["nodes"] if l["name"] != "needs-human"]
        self.data(s)
        self.assertEqual(self.tick_as("Mini-Two")[0], ["#1"])  # the old stamp doesn't hold it
        self.ticket().mark_claimed("b", "Mini-Two")
        self.assertEqual(self.tick_as("Mini-One")[0], [])
        self.assertEqual(self.ticket().claimed_by, "Mini-Two")


class GitHubTick(unittest.TestCase):
    """A real tick: stub agent, stub check, fake gh. One ready issue ends closed."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT")}
        os.environ["RUNWAY_HOME"] = str(self.home)
        w = GitHubWrites("test_claim_assigns_and_comments_machine_and_branch")
        w.setUp()
        self.w = w

    def tearDown(self):
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def run_tick(self, check):
        w = self.w
        w.data(issue(1, title="Do the thing"))
        root = make_repo({}, check=check)
        os.environ["HB_ROOT"] = str(root)
        cfg = dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))
        cfg.update(w.cfg)
        with mock.patch.object(runway, "machine_name", return_value="Mini-One"):
            runway.tick(cfg, root, runway.make_tracker(cfg, root))
        return w.stored()

    def test_ready_to_closed(self):
        s = self.run_tick("true")
        self.assertEqual((s["state"], s["stateReason"]), ("CLOSED", "COMPLETED"))
        bodies = [c["body"] for c in s["comments"]["nodes"]]
        self.assertIn("Claimed-by: Mini-One", bodies[0])
        self.assertIn("check passed, merged into `runway/integration`", bodies[-1])

    def test_failed_check_parks_it(self):
        s = self.run_tick("false")
        self.assertEqual(s["state"], "OPEN")
        self.assertIn("needs-human", [l["name"] for l in s["labels"]["nodes"]])
        self.assertEqual(s["assignees"]["totalCount"], 0)
        self.assertIn("Parked:", s["comments"]["nodes"][-1]["body"])


if __name__ == "__main__":
    unittest.main()
