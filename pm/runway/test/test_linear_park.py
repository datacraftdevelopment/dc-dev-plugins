"""Offline tests: an approved Linear ticket that parks waits for a fresh go (gh-13).
Run: python3 -m pytest -q test_linear_park.py"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linear_tracker as L  # noqa: E402

LABELS = {n: f"id-{n}" for n in ("ready-for-agent", "ready-for-human", "go", "needs-human")}


class StatefulApi:
    """Answers the reads from one canned issue node and applies issueUpdate / commentCreate to it."""

    def __init__(self, node):
        self.node = node

    def gql(self, query, variables=None, landed=None):
        if query is L.Q_ISSUES:
            return {"issues": {"nodes": [self.node], "pageInfo": {"hasNextPage": False, "endCursor": None}}}
        if query is L.M_UPDATE:
            i, n = variables["input"], self.node
            by_id = {v: k for k, v in LABELS.items()}
            keep = [x for x in n["labels"]["nodes"] if x["id"] not in i.get("removedLabelIds", [])]
            keep += [{"id": x, "name": by_id[x]} for x in i.get("addedLabelIds", [])]
            n["labels"]["nodes"] = keep
            if "stateId" in i:  # the only state the fake team has is unstarted
                n["state"] = {"type": "unstarted"}
        elif query is L.M_COMMENT:
            k = len(self.node["comments"]["nodes"]) + 1
            self.node["comments"]["nodes"].append(
                {"body": variables["input"]["body"], "createdAt": f"2026-10-09T10:{k:02d}"})
        return {}


def make(labels):
    node = {"id": "uuid-1", "identifier": "DAT-1", "number": 1, "title": "t", "description": "",
            "url": "https://linear.app/x/issue/DAT-1", "state": {"type": "started"},
            "labels": {"nodes": [{"id": LABELS[n], "name": n} for n in labels]},
            "comments": {"nodes": []}, "inverseRelations": {"nodes": []}}
    tr = L.LinearTracker.__new__(L.LinearTracker)
    tr.root, tr.c, tr.api = Path(tempfile.mkdtemp()), dict(L.DEFAULTS, team="DAT"), StatefulApi(node)
    tr._team = {"all_labels": dict(LABELS),
                "states": {"nodes": [{"id": "s-un", "name": "Todo", "type": "unstarted", "position": 0}]}}
    return tr, node


def names(node):
    return [x["name"] for x in node["labels"]["nodes"]]


class LinearPark(unittest.TestCase):
    def park_approved(self):
        tr, node = make(["ready-for-human", "go"])
        tr.load()[0].mark_needs_human("checks failed", "boom")
        return tr, node

    def test_park_drops_go_and_adds_needs_human_in_one_update(self):
        tr, node = make(["ready-for-human", "go"])
        with mock.patch.object(tr.api, "gql", wraps=tr.api.gql) as g:
            tr.load()[0].mark_needs_human("checks failed", "boom")
        labelled = [c for c in g.call_args_list if c.args[0] is L.M_UPDATE and "addedLabelIds" in c.args[1]["input"]]
        self.assertEqual(len(labelled), 1)
        self.assertEqual(labelled[0].args[1]["input"]["removedLabelIds"], [LABELS["go"]])
        self.assertEqual(sorted(names(node)), ["needs-human", "ready-for-human"])
        self.assertIn("Comment `go` (or re-add the `go` label) to retry.", node["comments"]["nodes"][-1]["body"])

    def test_park_is_one_issue_update_for_state_and_labels(self):
        tr, node = make(["ready-for-human", "go"])
        with mock.patch.object(tr.api, "gql", wraps=tr.api.gql) as g:
            tr.load()[0].mark_needs_human("checks failed", "boom")
        updates = [c.args[1]["input"] for c in g.call_args_list if c.args[0] is L.M_UPDATE]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0], {"stateId": "s-un", "addedLabelIds": [LABELS["needs-human"]],
                                      "removedLabelIds": [LABELS["go"]]})

    def test_release_is_one_issue_update_and_keeps_go(self):
        tr, node = make(["ready-for-human", "go"])
        with mock.patch.object(tr.api, "gql", wraps=tr.api.gql) as g:
            tr.load()[0].mark_ready("stopped by pause")
        updates = [c.args[1]["input"] for c in g.call_args_list if c.args[0] is L.M_UPDATE]
        self.assertEqual(updates, [{"stateId": "s-un"}])

    def test_park_then_sync_stays_parked(self):
        tr, node = self.park_approved()
        for _ in range(3):
            tr.sync()
            t = tr.load()[0]
            self.assertEqual((t.status, t.gate), ("needs-human", "human"))
        self.assertEqual(len(node["comments"]["nodes"]), 1)  # just the park comment, no Approved churn

    def test_park_then_go_comment_approves(self):
        tr, node = self.park_approved()
        node["comments"]["nodes"].append({"body": "go", "createdAt": "2026-10-10T10:00"})
        tr.sync()
        t = tr.load()[0]
        self.assertEqual((t.status, t.gate), ("ready", "approved"))

    def test_park_then_go_label_readded_approves(self):
        tr, node = self.park_approved()
        node["labels"]["nodes"].append({"id": LABELS["go"], "name": "go"})
        tr.sync()
        t = tr.load()[0]
        self.assertEqual((t.status, t.gate), ("ready", "approved"))

    def test_parked_ready_for_agent_is_ready_when_the_label_is_removed(self):
        tr, node = make(["ready-for-agent"])
        tr.load()[0].mark_needs_human("x", "d")
        tr.sync()
        self.assertEqual(tr.load()[0].status, "needs-human")
        self.assertIn("Remove `needs-human` or comment `go` to retry.", node["comments"]["nodes"][-1]["body"])
        node["labels"]["nodes"] = [x for x in node["labels"]["nodes"] if x["name"] != "needs-human"]
        self.assertEqual(tr.load()[0].status, "ready")

    def test_release_keeps_go(self):
        tr, node = make(["ready-for-human", "go"])
        tr.load()[0].mark_ready("stopped by pause")
        self.assertIn("go", names(node))
        self.assertEqual(tr.load()[0].gate, "approved")


if __name__ == "__main__":
    unittest.main()
