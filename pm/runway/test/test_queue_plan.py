"""Pure tests for the queue plan: fake tickets in, a QueuePlan out, no I/O.
Run: python3 -m unittest -v test_queue_plan"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import queue_plan as qp  # noqa: E402

ME = "mini-1"
CFG = {"harness": "claude", "agent_cmd": "a", "prep_cmd": "p",
       "harnesses": {"codex": {"agent_cmd": "cx", "parser": "codex"}}}


class T:
    """The ticket interface the plan reads: id, effort, num, gate, status, claimed_by, blocked_by, harness."""

    def __init__(self, num, gate="auto", status="ready", blocked_by=(), claimed_by=None, harness=None, effort="e"):
        self.effort, self.num, self.gate, self.status = effort, str(num).zfill(2), gate, status
        self.blocked_by, self.claimed_by, self.harness = [str(b).zfill(2) for b in blocked_by], claimed_by, harness
        self.id = f"{effort}/{self.num}"


def plan(tickets, finish="all_done", cfg=CFG, machine=ME):
    return qp.plan(tickets, machine, finish, cfg)


def steps(p):
    return {s.id: s.kind for s in p.steps}


class EveryStep(unittest.TestCase):
    def test_each_step(self):
        ts = [T(1, status="resolved"), T(2, status="claimed", claimed_by=ME),
              T(3, status="claimed", claimed_by="other"), T(4, status="claimed"),
              T(5, gate="human", status="needs-human"), T(6),
              T(7), T(8, gate="human"), T(9, blocked_by=[5]), T(10, harness="nope")]
        p = plan(ts)
        self.assertEqual(steps(p), {
            "e/01": "done", "e/02": "running_here", "e/03": "running_elsewhere",
            "e/04": "claimed_unknown_owner", "e/05": "waiting", "e/06": "run", "e/07": "queued",
            "e/08": "prep", "e/09": "blocked", "e/10": "park"})
        self.assertEqual(p.run_now.id, "e/06")
        self.assertEqual([t.id for t in p.prep], ["e/08"])
        self.assertEqual([s.id for s in p.park], ["e/10"])

    def test_steps_in_tracker_order_with_reasons(self):
        p = plan([T(2), T(1, gate="human", status="needs-human")])
        self.assertEqual([s.id for s in p.steps], ["e/02", "e/01"])
        self.assertTrue(all(s.reason for s in p.steps))

    def test_not_runways_left_out(self):
        self.assertEqual(plan([T(1, gate="wayfinder"), T(2, gate="none")]).steps, [])

    def test_status_outside_the_steps_left_out(self):
        self.assertEqual(plan([T(1, status="weird")]).steps, [])

    def test_empty_queue(self):
        p = plan([])
        self.assertEqual((p.steps, p.run_now, p.prep, p.park, p.harnesses_needed), ([], None, [], [], []))


class Precedence(unittest.TestCase):
    def test_bad_harness_parks_first_whatever_gate_or_owner(self):
        for t in (T(1, gate="human"), T(1, claimed_by="other"), T(1, blocked_by=[9]), T(1, gate="none")):
            t.harness = "nope"
            p = plan([t, T(9, status="needs-human", gate="human")] if t.blocked_by else [t])
            self.assertEqual([s.id for s in p.park], ["e/01"], t.gate)
            self.assertIn("unknown harness 'nope'", p.park[0].reason)
            self.assertIsNone(p.run_now)

    def test_park_includes_tickets_that_are_not_runways(self):
        p = plan([T(1, gate="none", harness="nope")])
        self.assertEqual([s.id for s in p.park], ["e/01"])
        self.assertEqual(p.steps, [])

    def test_bad_harness_on_a_claimed_ticket_does_not_park(self):
        p = plan([T(1, status="claimed", claimed_by=ME, harness="nope")])
        self.assertEqual(p.park, [])
        self.assertEqual(steps(p), {"e/01": "running_here"})

    def test_lookahead_ignores_claim_stamps(self):
        p = plan([T(1, gate="human", claimed_by="other")])
        self.assertEqual(steps(p), {"e/01": "prep"})

    def test_runnable_owned_by_another_mac_runs_elsewhere(self):
        p = plan([T(1, claimed_by="other"), T(2)])
        self.assertEqual(steps(p)["e/01"], "running_elsewhere")
        self.assertEqual(p.run_now.id, "e/02")

    def test_runnable_stamped_with_this_mac_runs(self):
        self.assertEqual(plan([T(1, claimed_by=ME)]).run_now.id, "e/01")

    def test_approved_gate_runs(self):
        self.assertEqual(plan([T(1, gate="approved")]).run_now.id, "e/01")


class Blockers(unittest.TestCase):
    def test_done_blocker_unblocks(self):
        self.assertEqual(plan([T(1, status="resolved"), T(2, blocked_by=[1])]).run_now.id, "e/02")

    def test_missing_blocker_counts_as_done(self):
        self.assertEqual(plan([T(2, blocked_by=[7])]).run_now.id, "e/02")

    def test_blockers_are_keyed_by_effort(self):
        a = T(2, blocked_by=[1], effort="x")
        other = T(1, effort="y")  # same num, different effort: not a blocker for x/02
        p = plan([a, other])
        self.assertEqual(steps(p), {"x/02": "run", "y/01": "queued"})

    def test_stub_blockers_count(self):
        stub = T(1, gate="none")  # a ticket that isn't Runway's still blocks
        p = plan([stub, T(2, blocked_by=[1])])
        self.assertEqual(steps(p), {"e/02": "blocked"})

    def test_blocked_reason_names_blockers(self):
        p = plan([T(1, status="claimed", claimed_by="other"), T(2, blocked_by=[1])])
        self.assertEqual(p.steps[1].reason, "blocked by e/01")

    def test_blocked_reason_says_when_chain_ends_at_joe(self):
        p = plan([T(1, gate="human", status="needs-human"), T(2, blocked_by=[1]), T(3, blocked_by=[2])])
        by = {s.id: s.reason for s in p.steps}
        self.assertEqual(by["e/02"], "blocked by e/01, waiting on you")
        self.assertEqual(by["e/03"], "blocked by e/02, waiting on you")

    def test_gated_behind_another_decision_is_blocked(self):
        p = plan([T(1, gate="human", status="needs-human"), T(2, gate="human", blocked_by=[1])])
        self.assertEqual(steps(p)["e/02"], "blocked")
        self.assertEqual(p.prep, [])

    def test_gated_behind_auto_work_is_prepped(self):
        p = plan([T(1), T(2, gate="human", blocked_by=[1])])
        self.assertEqual(steps(p), {"e/01": "run", "e/02": "prep"})

    def test_gated_behind_a_claimed_auto_blocker_is_prepped(self):
        p = plan([T(1, status="claimed", claimed_by="other"), T(2, gate="human", blocked_by=[1])])
        self.assertEqual(steps(p)["e/02"], "prep")

    def test_gated_behind_a_waiting_auto_ticket_is_blocked(self):
        p = plan([T(1, status="needs-human"), T(2, gate="human", blocked_by=[1])])
        self.assertEqual(steps(p)["e/02"], "blocked")

    def test_cycle_is_never_lookahead_eligible(self):
        p = plan([T(1, gate="human", blocked_by=[2]), T(2, blocked_by=[1])])
        self.assertEqual(steps(p), {"e/01": "blocked", "e/02": "blocked"})
        self.assertEqual(p.prep, [])
        self.assertIsNone(p.run_now)

    def test_self_cycle(self):
        p = plan([T(1, gate="human", blocked_by=[1])])
        self.assertEqual(steps(p), {"e/01": "blocked"})

    def test_cycle_reason_does_not_loop(self):
        p = plan([T(1, blocked_by=[2]), T(2, blocked_by=[1])])
        self.assertIn("cycle", p.idle_reason)


class Claims(unittest.TestCase):
    def test_claim_with_no_machine_stamp(self):
        p = plan([T(1, status="claimed")])
        self.assertEqual(steps(p), {"e/01": "claimed_unknown_owner"})
        self.assertIn("no machine", p.steps[0].reason)

    def test_claim_reasons_name_the_machine(self):
        p = plan([T(1, status="claimed", claimed_by="other")])
        self.assertIn("other", p.steps[0].reason)

    def test_one_run_per_plan(self):
        p = plan([T(1), T(2), T(3)])
        self.assertEqual((p.run_now.id, [s.kind for s in p.steps]), ("e/01", ["run", "queued", "queued"]))

    def test_prep_covers_every_eligible_gated_ticket(self):
        p = plan([T(1, gate="human"), T(2, gate="human"), T(3)])
        self.assertEqual([t.id for t in p.prep], ["e/01", "e/02"])
        self.assertEqual(p.run_now.id, "e/03")


class HarnessesNeeded(unittest.TestCase):
    def test_run_queued_and_prep_candidates(self):
        p = plan([T(1, harness="codex"), T(2), T(3, gate="human", harness="codex"),
                  T(4, status="needs-human", gate="human", harness="codex")])
        self.assertEqual(p.harnesses_needed, ["codex", "claude"])

    def test_default_harness_comes_from_config(self):
        p = plan([T(1)], cfg=dict(CFG, harness="codex"))
        self.assertEqual(p.harnesses_needed, ["codex"])

    def test_bad_harness_and_other_macs_work_need_nothing(self):
        p = plan([T(1, harness="nope"), T(2, claimed_by="other"), T(3, status="claimed", claimed_by=ME)])
        self.assertEqual(p.harnesses_needed, [])

    def test_blocked_needs_nothing(self):
        p = plan([T(1, status="needs-human"), T(2, blocked_by=[1])])
        self.assertEqual(p.harnesses_needed, [])


class HarnessRules(unittest.TestCase):
    def test_unknown_label_errors_known_ones_do_not(self):
        self.assertIn("known: claude, codex", qp.harness_error(CFG, T(1, harness="nope")))
        for ok in (None, "claude", "Codex"):
            self.assertIsNone(qp.harness_error(CFG, T(1, harness=ok)))

    def test_profile_overlays_top_level_commands(self):
        prof = qp.resolve_harness(CFG, T(1, harness="codex"))
        self.assertEqual((prof["agent_cmd"], prof["prep_cmd"], prof["parser"], prof["name"]),
                         ("cx", "p", "codex", "codex"))

    def test_fallback_to_top_level_commands(self):
        prof = qp.resolve_harness(CFG, T(1, harness="nope"))
        self.assertEqual((prof["agent_cmd"], prof["name"], prof["parser"]), ("a", "claude", "claude"))


class Finish(unittest.TestCase):
    def verdict(self, tickets, mode="all_done"):
        return plan(tickets, finish=mode).finish

    def test_all_done_finishes(self):
        f = self.verdict([T(1, status="resolved")])
        self.assertEqual(f.verdict, "finish")

    def test_empty_queue_counts_as_all_done(self):
        self.assertEqual(self.verdict([]).verdict, "finish")

    def test_claimed_waits(self):
        f = self.verdict([T(1, status="claimed", claimed_by="other"), T(2, status="resolved")], "idle")
        self.assertEqual(f.verdict, "wait")
        self.assertIn("claimed", f.reason)

    def test_open_under_all_done_waits_with_count(self):
        f = self.verdict([T(1), T(2, status="needs-human"), T(3, status="resolved")])
        self.assertEqual(f.verdict, "wait")
        self.assertIn("2 open", f.reason)

    def test_idle_ignores_open_tickets(self):
        self.assertEqual(self.verdict([T(1)], "idle").verdict, "finish")

    def test_unknown_mode_behaves_like_idle(self):
        self.assertEqual(self.verdict([T(1)], "sometimes").verdict, "finish")
        self.assertEqual(self.verdict([T(1, status="claimed")], "sometimes").verdict, "wait")

    def test_off_wins(self):
        for ts in ([], [T(1, status="claimed")], [T(1)]):
            self.assertEqual(self.verdict(ts, "off").verdict, "off")

    def test_only_runways_tickets_count(self):
        self.assertEqual(self.verdict([T(1, gate="wayfinder"), T(2, status="resolved")]).verdict, "finish")

    def test_claimed_ticket_of_any_gate_in_runways_set_only(self):
        self.assertEqual(self.verdict([T(1, gate="none", status="claimed")], "idle").verdict, "finish")


class IdleReason(unittest.TestCase):
    def test_none_when_something_can_run(self):
        self.assertIsNone(plan([T(1), T(2, blocked_by=[1])]).idle_reason)

    def test_counts_what_waits_on_joe(self):
        ts = [T(7, gate="human", status="needs-human")] + [T(n, blocked_by=[7]) for n in range(10, 29)]
        p = plan(ts)
        self.assertIsNone(p.run_now)
        self.assertEqual(p.idle_reason, "nothing can run: 19 tickets wait on e/07 (waiting on you)")

    def test_transitive_chain_counts_against_the_root(self):
        ts = [T(1, status="needs-human"), T(2, blocked_by=[1]), T(3, blocked_by=[2])]
        self.assertEqual(plan(ts).idle_reason, "nothing can run: 2 tickets wait on e/01 (waiting on you)")

    def test_one_ticket_is_singular(self):
        ts = [T(1, status="needs-human"), T(2, blocked_by=[1])]
        self.assertEqual(plan(ts).idle_reason, "nothing can run: 1 ticket waits on e/01 (waiting on you)")

    def test_root_that_is_not_joe(self):
        ts = [T(1, status="claimed", claimed_by="other"), T(2, blocked_by=[1])]
        self.assertEqual(plan(ts).idle_reason, "nothing can run: 1 ticket waits on e/01")

    def test_multiple_roots(self):
        ts = [T(1, status="needs-human"), T(2, status="needs-human"),
              T(3, blocked_by=[1]), T(4, blocked_by=[2]), T(5, blocked_by=[2])]
        r = plan(ts).idle_reason
        self.assertIn("1 ticket waits on e/01 (waiting on you)", r)
        self.assertIn("2 tickets wait on e/02 (waiting on you)", r)

    def test_bad_harness_park_is_counted(self):
        r = plan([T(1, harness="nope")]).idle_reason
        self.assertEqual(r, "nothing can run: 1 ticket is parked on a bad harness label")

    def test_nothing_ready(self):
        self.assertEqual(plan([]).idle_reason, "nothing can run: no ticket is ready")
        self.assertEqual(plan([T(1, status="resolved")]).idle_reason, "nothing can run: no ticket is ready")

    def test_prep_only_is_not_idle_of_work_but_run_now_is_none(self):
        r = plan([T(1, gate="human")]).idle_reason
        self.assertEqual(r, "nothing can run: 1 ticket needs prep first")


if __name__ == "__main__":
    unittest.main()
