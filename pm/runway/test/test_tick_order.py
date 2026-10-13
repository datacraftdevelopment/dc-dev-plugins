"""The tick follows the queue plan, in order: sign-in check before any change, parks in order, and the run
picked from the reload after sync_base. Run: python3 -m unittest -v test_tick_order"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402


class T:
    def __init__(self, id, num, gate="auto", status="ready", harness=None, blocked_by=(), claimed_by=None, events=None):
        self.id, self.num, self.effort, self.gate, self.status = id, num, "eff", gate, status
        self.harness, self.blocked_by, self.claimed_by, self.events = harness, list(blocked_by), claimed_by, events

    def mark_needs_human(self, why, detail):
        self.status = "needs-human"
        self.events.append(f"park {self.id}")


class Tracker:
    def __init__(self, loads):
        self.loads = list(loads)
        self.n = 0

    def sync(self):
        pass

    def load(self):
        self.n += 1
        return self.loads.pop(0) if len(self.loads) > 1 else self.loads[0]


class TickOrder(unittest.TestCase):
    def tick(self, tr, signin=False, harnesses=None):
        ev = self.events
        cfg = {**runway.DEFAULT_CONFIG}
        root = Path(tempfile.mkdtemp())

        def signin_check(c, r, names, *a, **k):
            ev.append(f"signin {list(names)}")
            return signin

        with mock.patch.object(runway, "machine_name", return_value="Mini-One"), \
                mock.patch.object(runway, "signin_waiting", side_effect=signin_check), \
                mock.patch.object(runway, "sync_base", side_effect=lambda c, r: ev.append("sync_base") or True), \
                mock.patch.object(runway, "prep", side_effect=lambda c, r, t: ev.append(f"prep {t.id}")), \
                mock.patch.object(runway, "run_ticket", side_effect=lambda c, r, tr_, t: ev.append(f"run {t.id}")), \
                mock.patch.object(runway, "release_orphans", return_value=False), \
                mock.patch.object(runway, "log"), mock.patch.object(runway, "beat"):
            return runway.tick(cfg, root, tr)

    def setUp(self):
        self.events = []

    def mk(self, *a, **k):
        return T(*a, events=self.events, **k)

    def test_signin_check_comes_before_any_change(self):
        tr = Tracker([[self.mk("eff/01", 1, harness="nope"), self.mk("eff/02", 2)]])
        self.assertFalse(self.tick(tr, signin=True))
        self.assertEqual(self.events, ["signin ['claude']"])  # no park, no prep, no sync_base, no run

    def test_signin_check_covers_queued_and_prep_candidates(self):
        tr = Tracker([[self.mk("eff/01", 1), self.mk("eff/02", 2, harness="claude"),
                       self.mk("eff/03", 3, gate="human")]])
        self.tick(tr, signin=True)
        self.assertEqual(self.events, ["signin ['claude']"])

    def test_parks_happen_in_order_then_prep_then_sync_then_run(self):
        a = self.mk("eff/01", 1, harness="nope")
        h = self.mk("eff/02", 2, gate="human")
        b = self.mk("eff/03", 3, harness="bad")
        c = self.mk("eff/04", 4)
        self.assertTrue(self.tick(Tracker([[a, h, b, c]])))
        self.assertEqual(self.events, ["signin ['claude']", "park eff/01", "prep eff/02", "park eff/03",
                                       "sync_base", "run eff/04"])

    def test_run_is_picked_from_the_reload_after_sync_base(self):
        first = [self.mk("eff/01", 1)]
        after = [self.mk("eff/01", 1, status="needs-human"), self.mk("eff/02", 2)]
        self.assertTrue(self.tick(Tracker([first, after])))
        self.assertEqual(self.events[-2:], ["sync_base", "run eff/02"])

    def test_second_pass_parks_a_label_that_went_bad(self):
        first = [self.mk("eff/01", 1)]
        after = [self.mk("eff/01", 1, harness="bad"), self.mk("eff/02", 2)]
        self.assertTrue(self.tick(Tracker([first, after])))
        self.assertEqual(self.events[-3:], ["sync_base", "park eff/01", "run eff/02"])

    def test_plan_rebuilds_only_at_reloads_no_extra_tracker_read(self):
        tr = Tracker([[self.mk("eff/01", 1, harness="nope"), self.mk("eff/02", 2)]])
        self.tick(tr)
        self.assertEqual(tr.n, 2)  # the first load and the reload after sync_base


if __name__ == "__main__":
    unittest.main()
