"""Offline tests for `runway status --json` (markdown tracker). Run: python3 -m unittest -v test_status_json"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402

TICKETS = {
    # file name: (header lines, body)
    "01-done-thing": ("Status: resolved", ""),
    "02-running": ("Status: claimed\nBranch: runway/x-02", ""),
    "03-ask": ("Status: needs-human\nGate: human\nWaiting on: Joe, go/no-go",
               "\n## Decision packet\n\n_Prepared._\n\nOld one\n\n## Decision packet\n\n_Prepared._\n\nPick A or B\n"),
    "04-auto-b": ("Blocked by: 01", ""),
    "05-auto-a": ("", ""),
    "06-prep": ("Gate: human", ""),
    "07-blocked": ("Blocked by: 02, 04", ""),
    "08-not-runways": ("Gate: wayfinder", ""),
}


def make_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    d = root / ".scratch" / "eff" / "issues"
    d.mkdir(parents=True)
    for name, (head, body) in TICKETS.items():
        (d / f"{name}.md").write_text(f"# Title {name}\n{head}\n{body}")
    return root


class StatusJson(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        self.tracker = runway.make_tracker({"tracker": "markdown"}, self.root)

    def doc(self):
        return runway.status_json({"tracker": "markdown"}, self.root, self.tracker)

    def test_shape_and_groups_in_queue_order(self):
        d = self.doc()
        self.assertEqual(d["version"], 1)
        self.assertEqual(d["repo"], str(self.root))
        self.assertEqual(d["tracker"], "markdown")
        self.assertRegex(d["generated_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        self.assertEqual(d["groups"], {
            "waiting": ["eff/03"], "running": ["eff/02"],
            "ready_auto": ["eff/04", "eff/05"], "ready_prep": ["eff/06"],
            "blocked": ["eff/07"], "done": ["eff/01"]})
        json.dumps(d)  # serializable

    def test_ticket_fields(self):
        by = {t["id"]: t for t in self.doc()["tickets"]}
        self.assertEqual(set(by), {"eff/0%d" % i for i in range(1, 8)})  # 08 is not Runway's
        w = by["eff/03"]
        self.assertEqual(set(w), {"id", "title", "url", "status", "gate", "blocked_by",
                                  "waiting_on", "packet", "harness", "claimed_by"})
        self.assertEqual(w["status"], "needs-human")
        self.assertEqual(w["gate"], "human")
        self.assertEqual(w["waiting_on"], "Joe, go/no-go")
        self.assertIn("Pick A or B", w["packet"])
        self.assertNotIn("Old one", w["packet"])
        self.assertEqual(w["harness"], "claude")
        self.assertEqual(by["eff/07"]["blocked_by"], ["eff/02", "eff/04"])
        self.assertIsNone(by["eff/07"]["packet"])
        self.assertIsNone(by["eff/07"]["waiting_on"])
        self.assertEqual(by["eff/05"]["url"], ".scratch/eff/issues/05-auto-a.md")

    def run_cli(self, *args):
        script = str(Path(runway.__file__))
        return subprocess.run([sys.executable, script, "--root", str(self.root), "status", *args],
                              capture_output=True, text=True, check=True).stdout

    def test_cli_json(self):
        self.assertEqual(json.loads(self.run_cli("--json"))["groups"]["done"], ["eff/01"])

    def test_text_output_unchanged(self):
        self.assertEqual(self.run_cli(), (
            "\nWaiting on you (1)\n  eff/03                   Title 03-ask  [Joe, go/no-go]\n"
            "\nRunning (1)\n  eff/02                   Title 02-running\n"
            "\nReady (auto) (2)\n  eff/04                   Title 04-auto-b\n  eff/05                   Title 05-auto-a\n"
            "\nReady (needs prep) (1)\n  eff/06                   Title 06-prep\n"
            "\nBlocked (1)\n  eff/07                   Title 07-blocked\n"
            "\nDone (1)\n  eff/01                   Title 01-done-thing\n"))


class FakeLinear:
    """Just enough of LinearTracker for status: load() over canned issue nodes, no API."""

    def __init__(self, nodes):
        import linear_tracker as L
        self.L, self.nodes, self.c = L, nodes, dict(L.DEFAULTS, team="DAT")

    def load(self):
        return [self.L.LinearTicket(n, self) for n in self.nodes]


def node(i, labels, state, comments=(), blocked_by=()):
    return {
        "id": f"uuid-{i}", "identifier": f"DAT-{i}", "number": i, "title": f"t{i}", "description": "",
        "url": f"https://linear.app/x/issue/DAT-{i}", "state": {"type": state},
        "labels": {"nodes": [{"id": n, "name": n} for n in labels]},
        "comments": {"nodes": [{"body": b, "createdAt": f"2026-01-0{k + 1}T00:00"} for k, b in enumerate(comments)]},
        "inverseRelations": {"nodes": [
            {"type": "blocks", "issue": {"identifier": b, "number": 0, "title": "", "state": {"type": "started"}}}
            for b in blocked_by]},
    }


class StatusJsonLinear(unittest.TestCase):
    def test_linear_shape(self):
        tr = FakeLinear([
            node(1, ["ready-for-agent"], "unstarted"),
            node(2, ["ready-for-human", "needs-human"], "unstarted",
                 ["Joe's first note", "\U0001f6eb runway · **Decision packet**\n\nPick A or B"]),
            node(3, ["ready-for-agent"], "unstarted", blocked_by=["DAT-1"]),
            node(5, [], "unstarted"),  # not Runway's
        ])
        d = runway.status_json({"tracker": "linear"}, Path("/r"), tr)
        self.assertEqual(d["tracker"], "linear")
        self.assertEqual(d["groups"]["waiting"], ["DAT-2"])
        self.assertEqual(d["groups"]["ready_auto"], ["DAT-1"])
        self.assertEqual(d["groups"]["blocked"], ["DAT-3"])
        by = {t["id"]: t for t in d["tickets"]}
        self.assertNotIn("DAT-5", by)
        self.assertEqual(by["DAT-2"]["url"], "https://linear.app/x/issue/DAT-2")
        self.assertEqual(by["DAT-2"]["gate"], "human")
        self.assertEqual(by["DAT-2"]["packet"], "**Decision packet**\n\nPick A or B")
        self.assertEqual(by["DAT-3"]["blocked_by"], ["DAT-1"])
        json.dumps(d)


if __name__ == "__main__":
    unittest.main()
