"""Offline tests (gh-43): a tracker write that fails halfway never leaves a ticket runnable without a go.
Every write of park, approve, resolve, drop and release is failed in turn, on both trackers' write orders
(the in-memory adapter configured as GitHub and as Linear), then sync runs again.
Run: python3 -m pytest -q test_write_boundaries.py"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ticket_protocol as P  # noqa: E402
from memory_adapter import MemoryTracker, issue  # noqa: E402

M = "\U0001f6eb runway"
RULES = (("github", P.GITHUB), ("linear", P.LINEAR))


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


def runnable(t) -> bool:
    return t.status == "ready" and t.gate in ("auto", "approved")


class Boundaries(unittest.TestCase):
    def build(self, rules, **kw):
        kw.setdefault("id", "#1" if rules is P.GITHUB else "DAT-1")
        tr = MemoryTracker(Path(tempfile.mkdtemp()), rules, [issue(**kw)])
        return tr, tr.issues[0]

    def sweep(self, scenario, act, check, mid=None):
        """Run `act` once to count its writes, then once per write with that write failing. After each failure
        the world is synced (as the next tick does) and `check` looks at the ticket."""
        for name, rules in RULES:
            tr, data = self.build(rules, **scenario)
            act(tr, tr.load()[0])
            total = tr.writes
            self.assertGreater(total, 0)
            for i in range(total):
                with self.subTest(tracker=name, failing_write=i, of=total):
                    tr, data = self.build(rules, **scenario)
                    tr.fail_at = i
                    try:
                        act(tr, tr.load()[0])
                    except RuntimeError:
                        pass
                    else:
                        self.fail("the write was meant to fail")
                    if mid:
                        mid(tr.load()[0])
                    quiet(tr.sync)
                    quiet(tr.sync)  # a second sync must change nothing more
                    check(tr, data, tr.load()[0])

    # -- park --

    def not_ready(self, t):  # straight after the failure, before any sync
        self.assertIn(t.status, ("claimed", "needs-human"))

    def park(self, tr, t):
        t.mark_needs_human("run failed", "boom")

    def parked(self, tr, data, t):
        self.assertEqual(t.status, "needs-human")
        self.assertFalse(runnable(t))
        self.assertNotIn("go", data["labels"])
        parks = [c for c in data["comments"] if "Parked: run failed" in c["body"]]
        self.assertEqual(len(parks), 1)
        self.assertEqual(len([c for c in data["comments"] if "Approved." in c["body"]]), 0)

    def test_park_of_an_approved_ticket(self):
        self.sweep(dict(labels=["ready-for-human", "go"], held=True,
                        comments=[(f"{M} · Claimed-by: Mini-One · Started on `b`.", True)]), self.park, self.parked)

    def test_park_with_a_go_posted_during_the_run(self):
        self.sweep(dict(labels=["ready-for-human", "go"], held=True,
                        comments=[(f"{M} · Claimed-by: Mini-One · Started on `b`.", True), ("go use plan B", True)]),
                   self.park, self.parked, self.not_ready)

    def test_park_of_an_agent_ticket_with_a_go_posted_during_the_run(self):
        self.sweep(dict(labels=["ready-for-agent"], held=True,
                        comments=[(f"{M} · Claimed-by: Mini-One · Started on `b`.", True), ("go", True)]),
                   self.park, lambda tr, data, t: (self.assertEqual(t.status, "needs-human"),
                                                   self.assertEqual(len([c for c in data["comments"]
                                                                         if "Parked:" in c["body"]]), 1)),
                   self.not_ready)

    # -- approve --

    def sync_once(self, tr, t):
        quiet(tr.sync)

    def approved(self, tr, data, t):
        self.assertEqual(t.status, "ready")
        self.assertIn(t.gate, ("approved", "auto"))
        self.assertNotIn("needs-human", data["labels"])
        notes = [c["body"] for c in data["comments"] if "Approved." in c["body"]]
        self.assertEqual(len(notes), 1)
        self.assertIn("use plan B", notes[0])

    def test_approve_by_comment(self):
        self.sweep(dict(labels=["ready-for-human", "needs-human"],
                        comments=[(f"{M} · Parked: x. Remove `needs-human` or comment `go` to retry.", True),
                                  ("go use plan B", True)]), self.sync_once, self.approved)

    def test_approve_a_parked_agent_ticket_by_comment(self):
        self.sweep(dict(labels=["ready-for-agent", "needs-human"],
                        comments=[(f"{M} · Parked: x. Remove `needs-human` or comment `go` to retry.", True),
                                  ("go use plan B", True)]), self.sync_once, self.approved)

    def test_approve_through_runway_go(self):
        # The command itself fails loudly when its first write fails: nothing was recorded and the ticket stays
        # parked. Once the note is down, a failed label write is finished by the next sync.
        def check(tr, data, t):
            if any("Approved." in c["body"] for c in data["comments"]):
                self.approved(tr, data, t)
            else:
                self.assertEqual(t.status, "needs-human")
        self.sweep(dict(labels=["ready-for-human", "needs-human"],
                        comments=[(f"{M} · **Decision packet**", True)]),
                   lambda tr, t: t.approve("use plan B"), check)

    # -- resolve, drop, release --

    def test_resolve(self):
        def check(tr, data, t):
            self.assertFalse(runnable(t))
        self.sweep(dict(labels=["ready-for-human", "go"], held=True),
                   lambda tr, t: t.mark_resolved("Done on `b`."), check)

    def test_drop(self):
        def check(tr, data, t):
            self.assertTrue(t.closed)
            self.assertFalse(runnable(t))
            # Linear closes, then comments: a failed comment leaves a closed ticket and no note, never a second note
            self.assertLessEqual(len([c for c in data["comments"] if "Dropped." in c["body"]]), 1)
        self.sweep(dict(labels=["ready-for-human", "needs-human"],
                        comments=[(f"{M} · Parked: x.", True), ("drop", True)]), self.sync_once, check)

    def test_release_keeps_go_and_never_loses_the_ticket(self):
        def check(tr, data, t):
            self.assertIn("go", data["labels"])
            self.assertNotIn("needs-human", data["labels"])
        self.sweep(dict(labels=["ready-for-human", "go"], held=True),
                   lambda tr, t: t.mark_ready("stopped by pause"), check)


if __name__ == "__main__":
    unittest.main()
