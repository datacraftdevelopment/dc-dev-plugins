"""Offline tests for settle(): one table row per Outcome kind, checked with a fake ticket, notify and record.
Run: python3 -m pytest -q test_settle.py. No git: `sh` is faked to capture the cleanup commands."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402

SIGN_IN = "Claude Code is signed out; Runway paused. Sign in, then `runway resume`."
PARK = ("needs-human", True, "needs-human", "park", True)
# kind: (ticket write, notify, result, last_result, worktree removed)
ROWS = {
    "stopped": ("ready", False, "stopped", None, False),
    "signed-out": ("ready", False, "signed-out", None, True),
    "merged": ("resolved", False, "done", "pass", True),
    "question": PARK, "agent-failed": PARK, "no-commits": PARK, "check-failed": PARK, "merge-conflict": PARK,
}


class FakeTicket:
    def __init__(self, calls):
        self.id, self.title, self.effort, self.slug = "01-thing", "Thing", "eff", "thing"
        self.calls = calls

    def mark_ready(self, note):
        self.calls.append(("write", "ready", note))

    def mark_resolved(self, note):
        self.calls.append(("write", "resolved", note))

    def mark_needs_human(self, why, detail):
        self.calls.append(("write", "needs-human", detail))


class Settle(unittest.TestCase):
    def settle(self, kind, detail=""):
        calls = []
        t = FakeTicket(calls)
        tracker = SimpleNamespace(reload=lambda x: (calls.append(("reload",)), x)[1])
        cfg = dict(runway.DEFAULT_CONFIG, worktree_dir="/tmp/wt-{repo}", integration_branch="integ")
        with mock.patch.object(runway, "notify", lambda c, r, m: calls.append(("notify", m))), \
             mock.patch.object(runway, "record", lambda r, rec: calls.append(("record", rec))), \
             mock.patch.object(runway, "beat_update", lambda r, **kw: calls.append(("beat", kw))), \
             mock.patch.object(runway, "log", lambda r, m: None), \
             mock.patch.object(runway, "sh", lambda cmd, cwd, **kw: calls.append(("sh", cmd))):
            runway.settle(cfg, Path("/tmp/repo"), tracker, t, runway.Outcome(kind, 2, detail))
        return calls

    def test_every_kind_follows_its_row(self):
        self.assertEqual(set(ROWS), set(runway.SETTLE))
        for kind, (write, notify, result, last, removed) in ROWS.items():
            with self.subTest(kind=kind):
                calls = self.settle(kind, "why")
                self.assertEqual(calls[0], ("reload",))
                self.assertEqual([c[1] for c in calls if c[0] == "write"], [write])
                self.assertEqual([c[1] for c in calls if c[0] == "notify"], ["Blocked: 01-thing Thing"] * notify)
                beats = [c[1] for c in calls if c[0] == "beat"]
                self.assertEqual(beats, [{"last_result": last}] if last else [])
                rec = next(c[1] for c in calls if c[0] == "record")
                self.assertEqual((rec["kind"], rec["ticket"], rec["attempts"], rec["result"], rec["outcome"]),
                                 ("outcome", "01-thing", 2, result, kind))
                rm = [c for c in calls if c[0] == "sh"]
                self.assertEqual(len(rm), int(removed))
                if removed:
                    self.assertEqual(rm[0][1][:4], ["git", "worktree", "remove", "--force"])
                self.assertFalse(any("branch" in c[1] for c in rm))  # every row keeps the branch

    def test_order_is_reload_write_notify_beat_record_cleanup(self):
        calls = self.settle("question", "why")
        self.assertEqual([c[0] for c in calls], ["reload", "write", "notify", "beat", "record", "sh"])

    def test_note_wording(self):
        self.assertEqual(self.settle("stopped")[1], ("write", "ready", "stopped by pause"))
        self.assertEqual(self.settle("signed-out")[1], ("write", "ready", SIGN_IN))
        self.assertEqual(self.settle("merged")[1][2], "Done on `runway/eff-thing`, check passed, merged into `integ`.")
        self.assertEqual(self.settle("check-failed", "boom")[1], ("write", "needs-human", "boom"))
        self.assertEqual(self.settle("no-commits", "")[1], ("write", "needs-human", "Agent run failed with no detail."))

    def test_record_detail_capped(self):
        rec = next(c[1] for c in self.settle("question", "x" * 900) if c[0] == "record")
        self.assertEqual(len(rec["detail"]), 500)


if __name__ == "__main__":
    unittest.main()
