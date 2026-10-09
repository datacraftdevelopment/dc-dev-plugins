"""Offline tests: the Linear adapter never runs a spec (labelled `spec`, or with child issues).
Run: python3 -m pytest -q test_linear_spec.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linear_tracker as L  # noqa: E402
import runway  # noqa: E402


def node(i, labels=("ready-for-agent",), state="unstarted", children=0, blocked_by=()):
    return {
        "id": f"uuid-{i}", "identifier": f"DAT-{i}", "number": i, "title": f"t{i}", "description": "",
        "url": f"https://linear.app/x/issue/DAT-{i}", "state": {"type": state},
        "labels": {"nodes": [{"id": n, "name": n} for n in labels]},
        "children": {"nodes": [{"id": f"c{k}"} for k in range(children)]},
        "comments": {"nodes": []},
        "inverseRelations": {"nodes": [
            {"type": "blocks", "issue": {"identifier": b, "number": 0, "title": "", "state": {"type": "started"}}}
            for b in blocked_by]},
    }


class FakeApi:
    def __init__(self, nodes):
        self.nodes = nodes

    def gql(self, query, variables=None, landed=None):
        return {"issues": {"nodes": self.nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}


class LinearSpec(unittest.TestCase):
    def load(self, nodes):
        self.root = Path(tempfile.mkdtemp())
        tr = L.LinearTracker.__new__(L.LinearTracker)
        tr.root, tr.c, tr.api, tr._team = self.root, dict(L.DEFAULTS, team="DAT"), FakeApi(nodes), None
        return {t.id: t for t in tr.load()}, tr

    def test_issue_with_child_issues_is_not_run_but_children_are(self):
        by, _ = self.load([node(1, children=2), node(2), node(3, blocked_by=["DAT-1"])])
        self.assertEqual([by[f"DAT-{i}"].gate for i in (1, 2, 3)], ["none", "auto", "auto"])
        self.assertFalse(runway.unblocked(by["DAT-3"], list(by.values())))  # an open spec still gates

    def test_spec_label_is_not_run_even_with_a_runway_label(self):
        by, tr = self.load([node(1, labels=("spec", "ready-for-agent")),
                            node(2, labels=("spec", "ready-for-human", "go")), node(3)])
        self.assertEqual([by[f"DAT-{i}"].gate for i in (1, 2, 3)], ["none", "none", "auto"])
        log = (self.root / "_pm" / "runway.log").read_text()
        self.assertEqual(log.count("DAT-1 is labelled spec"), 1)
        tr.load()
        self.assertEqual((self.root / "_pm" / "runway.log").read_text(), log)

    def test_closed_spec_unblocks_its_dependents(self):
        by, _ = self.load([node(1, labels=("spec", "ready-for-agent"), state="completed"),
                           node(2, blocked_by=["DAT-1"])])
        by["DAT-2"].node["inverseRelations"]["nodes"][0]["issue"]["state"]["type"] = "completed"
        self.assertTrue(runway.unblocked(by["DAT-2"], list(by.values())))


if __name__ == "__main__":
    unittest.main()
