"""Offline tests: a long ticket keeps its claim owner and Joe's latest go, on both trackers, around the 25 and 50
comment marks. GitHub through a fake `gh`, Linear through a fake API. Run: python3 -m pytest -q test_long_ticket.py"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linear_tracker as L  # noqa: E402
import runway  # noqa: E402

M = "\U0001f6eb runway"
STAMP = M + " · Claimed-by: {} · Started on `b`."
MARKS = (23, 24, 25, 26, 48, 49, 50, 51, 120)  # notes between the two stamps and Joe's go


def history(chatter):
    """Comments, oldest first: two stamps (Mini-One first), `chatter` notes, then Joe's `go`."""
    return [STAMP.format("Mini-One"), STAMP.format("Mini-Two")] + [f"note {i}" for i in range(chatter)] + ["go ahead"]


def stamped(bodies):
    return [{"body": b, "createdAt": f"2026-10-01T{i // 3600:02d}:{i // 60 % 60:02d}:{i % 60:02d}Z",
             "authorAssociation": "OWNER"} for i, b in enumerate(bodies)]


def window(all_, end=None, size=50):
    """The last `size` comments before index `end` (GraphQL `last` / `before`), with its page info."""
    end = len(all_) if end is None else end
    start = max(0, end - size)
    return {"pageInfo": {"hasPreviousPage": start > 0, "startCursor": str(start)}, "nodes": all_[start:end]}


FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
data = json.load(open(os.environ["FAKE_GH_DATA"]))
with open(os.environ["FAKE_GH_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
q = next(a[6:] for a in sys.argv if a.startswith("query="))
def window(all_, end, size=50):
    start = max(0, end - size)
    return {"pageInfo": {"hasPreviousPage": start > 0, "startCursor": str(start)}, "nodes": all_[start:end]}
if "before: $before" in q:
    before = int(next(a[7:] for a in sys.argv if a.startswith("before=")))
    print(json.dumps({"data": {"repository": {"issue": {"comments": window(data["comments"], before)}}}}))
else:
    node = dict(data["node"], comments=window(data["comments"], len(data["comments"])))
    print(json.dumps({"data": {"repository": {"issues": {"nodes": [node], "pageInfo": {"hasNextPage": False}}}}}))
'''


class GitHubLong(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()).resolve()
        gh = self.dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        os.environ["FAKE_GH_DATA"] = str(self.dir / "data.json")
        os.environ["FAKE_GH_LOG"] = str(self.dir / "log")
        self.cfg = {"tracker": "github", "github": {"repo": "o/r", "gh": str(gh)}}

    def load(self, bodies, labels=("ready-for-agent",)):
        node = {"number": 1, "title": "T", "body": "", "url": "https://github.com/o/r/issues/1", "state": "OPEN",
                "stateReason": None, "labels": {"nodes": [{"name": n} for n in labels]},
                "assignees": {"totalCount": 1}, "subIssues": {"totalCount": 0}, "blockedBy": {"nodes": []}}
        (self.dir / "data.json").write_text(json.dumps({"node": node, "comments": stamped(bodies)}))
        (self.dir / "log").write_text("")
        return runway.make_tracker(self.cfg, self.dir).load()[0]

    def calls(self):
        return len((self.dir / "log").read_text().splitlines())

    def test_latest_go_is_seen_and_the_owner_is_unchanged(self):
        for chatter in MARKS:
            t = self.load(history(chatter))
            self.assertEqual(t.joe_replies()[-1], "go ahead", chatter)
            self.assertEqual(t.claimed_by, "Mini-One", chatter)

    def test_extra_calls_only_when_the_owner_needs_paging_back(self):
        t = self.load(history(10))
        self.assertEqual(t.claimed_by, "Mini-One")
        self.assertEqual(self.calls(), 1)  # the whole history fit the window
        t = self.load(history(120))
        self.assertEqual(t.claimed_by, "Mini-One")
        self.assertEqual(self.calls(), 1 + 2)  # 123 comments: the window plus two older pages
        t = self.load(history(120), labels=("ready-for-agent", "needs-human"))
        self.assertIsNone(t.claimed_by)
        self.assertEqual(self.calls(), 3)  # parked: shared barriers still require history


class LinearApi:
    def __init__(self, all_):
        self.all, self.calls = all_, 0

    def gql(self, query, variables=None, landed=None):
        self.calls += 1
        end = int(variables["before"]) if "before" in variables else len(self.all)
        return {"issue": {"comments": window(self.all, end)}}


class LinearLong(unittest.TestCase):
    def ticket(self, bodies):
        all_ = [{"body": c["body"], "createdAt": c["createdAt"]} for c in stamped(bodies)]
        api = LinearApi(all_)
        tr = type("Tr", (), {"c": dict(L.DEFAULTS, team="DAT"), "api": api})()
        node = {"id": "uuid-1", "identifier": "DAT-1", "number": 1, "title": "t", "description": "",
                "url": "u", "state": {"type": "started"}, "labels": {"nodes": []},
                "comments": window(all_), "inverseRelations": {"nodes": []}}
        return L.LinearTicket(node, tr), api

    def test_latest_go_is_seen_and_the_owner_is_unchanged(self):
        for chatter in MARKS:
            t, _ = self.ticket(history(chatter))
            self.assertEqual(t.joe_replies()[-1], "go ahead", chatter)
            self.assertEqual(t.claimed_by, "Mini-One", chatter)

    def test_paging_back_costs_calls_only_when_needed(self):
        t, api = self.ticket(history(10))
        self.assertEqual(t.claimed_by, "Mini-One")
        self.assertEqual(api.calls, 0)
        t, api = self.ticket(history(120))
        self.assertEqual(t.claimed_by, "Mini-One")
        self.assertEqual(api.calls, 2)


if __name__ == "__main__":
    unittest.main()
