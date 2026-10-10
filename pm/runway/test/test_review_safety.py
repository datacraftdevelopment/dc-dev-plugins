"""Offline merge coverage and two-root park/reopen regressions; no external calls."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import acceptance
import runway
import ticket_protocol as P
from memory_adapter import MemoryTracker, issue


class Coverage(unittest.TestCase):
    def test_inventory_uses_complete_original_body_not_comments_or_truncation(self):
        t=SimpleNamespace(id='#1',body='x'*5000+'\n## Acceptance\n- exact criterion\n',text='wrong')
        rows,errors=acceptance.inventory([t])
        self.assertFalse(errors);self.assertEqual(rows[0]['criterion'],'exact criterion')
        self.assertEqual(rows,acceptance.inventory([t])[0])

    def test_ambiguous_inventory_fails_closed(self):
        for body in ('no section','## Acceptance\nprose','## Acceptance\n- a\n- a'):
            self.assertTrue(acceptance.inventory([SimpleNamespace(id='#1',body=body)])[1])

    def test_complete_unique_evidence_required(self):
        expected,_=acceptance.inventory([SimpleNamespace(id='#1',body='## Acceptance\n- a\n- b')])
        good=[dict(r,evidence='test passes') for r in expected]
        self.assertFalse(acceptance.coverage(expected,good))
        for rows in ([],good[:1],good+good[:1],[dict(good[0],id='unknown'),good[1]],
                     [dict(good[0],criterion='different'),good[1]],[dict(good[0],evidence=''),good[1]]):
            with self.subTest(rows=rows):self.assertTrue(acceptance.coverage(expected,rows))

    def test_missing_criteria_refuses_pass(self):
        expected,_=acceptance.inventory([SimpleNamespace(id='#1',body='## Acceptance\n- a')])
        self.assertEqual(runway.decide_verdict(0,{'verdict':'pass','blocking':[], 'non_blocking':[], 'criteria':[]},1,expected)['verdict'],'fail')

    def test_finish_refuses_mocked_merge_when_judge_omits_inventory(self):
        import json
        from test_merge_on_pass import DraftMerge
        case = DraftMerge()
        case.setUp()
        original = case._agent
        def incomplete(*args, **kwargs):
            r, text = original(*args, **kwargs)
            if args[6] == "judge":
                text = json.dumps({"verdict":"pass", "blocking":[], "criteria":[]})
            return r, text
        runway.run_agent = incomplete
        try:
            with contextlib.redirect_stdout(io.StringIO()):case.finish()
            self.assertFalse(any(cmd[:3] == ["gh", "pr", "merge"] for cmd in case.gh))
            self.assertIn("Omitted acceptance criterion", (case.root / "_pm/runway-review.md").read_text())
        finally:
            case.tearDown();case.doCleanups()


class SharedParks(unittest.TestCase):
    def test_every_boundary_across_roots_and_closed_fixes(self):
        for rules in (P.GITHUB,P.LINEAR):
            for closed in (False,True):
                probe=MemoryTracker(Path(tempfile.mkdtemp()),rules,[issue('#1',closed=closed,held=not closed,labels=['ready-for-human','go'])])
                probe.load()[0].mark_needs_human('failed','both reviews')
                total=probe.writes
                for fail in range(total):
                    with self.subTest(tracker=rules.name,closed=closed,write=fail):
                        data=issue('#1',closed=closed,held=not closed,labels=['ready-for-human','go'],comments=[('go old approval',True)])
                        a=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data]);a.fail_at=fail
                        with self.assertRaises(RuntimeError):a.load()[0].mark_needs_human('failed','both reviews')
                        b=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data])
                        with contextlib.redirect_stdout(io.StringIO()):b.sync()
                        self.assertFalse(b.load()[0].status=='ready' and b.load()[0].gate in ('auto','approved'))
                        with contextlib.redirect_stdout(io.StringIO()):a.sync();b.sync()
                        t=b.load()[0]
                        self.assertEqual(t.status,'needs-human');self.assertFalse(t.closed);self.assertNotIn('go',t.labels)
                        self.assertIn('both reviews',t.packet)
                        # A genuinely fresh approval after completion remains valid.
                        data['comments'].append({'body':'go fresh','createdAt':'2026-12-01T00:00:00Z','trusted':True,'who':'Joe','assoc':'OWNER'})
                        with contextlib.redirect_stdout(io.StringIO() ):a.sync()
                        self.assertEqual(b.load()[0].gate,'approved');self.assertEqual(b.load()[0].status,'ready')

    def test_terminal_drop_after_completed_park_is_resolved(self):
        for rules in (P.GITHUB,P.LINEAR):
            tr=MemoryTracker(Path(tempfile.mkdtemp()),rules,[issue("#1",held=True,labels=["ready-for-human","go"])])
            tr.load()[0].mark_needs_human("failed","detail")
            tr.load()[0].decline("drop requested")
            self.assertTrue(tr.load()[0].closed)
            self.assertEqual(tr.load()[0].status,"resolved")

    def test_foreign_owner_cannot_reconcile_and_stale_owner_cannot_undo_new_claim(self):
        for rules in (P.GITHUB,P.LINEAR):
            data=issue("#1",held=True,labels=["ready-for-human","go"])
            a=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data]);a.fail_at=1
            with self.assertRaises(RuntimeError):a.load()[0].mark_needs_human("failed","detail")
            stale=a.load()[0];rec=stale.park_intent
            b=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data])
            self.assertFalse(b.complete_park(b.load()[0],rec));self.assertEqual(b.writes,0)
            with self.assertRaises(RuntimeError):b.load()[0].approve("premature")
            with self.assertRaises(RuntimeError):b.load()[0].mark_claimed("branch","other")
            self.assertTrue(a.complete_park(stale,rec))
            data["comments"].append({"body":"go fresh","createdAt":"2026-12-01T00:00:00Z","trusted":True,"who":"Joe","assoc":"OWNER"})
            b.now="2026-12-02T00:00:00Z"
            with contextlib.redirect_stdout(io.StringIO()):a.sync()
            with self.assertRaises(RuntimeError):b.load()[0].mark_claimed("branch","other")
            a.load()[0].mark_claimed("branch","writer")
            before=list(data["comments"])
            self.assertFalse(a.complete_park(stale,rec))
            self.assertTrue(data["held"]);self.assertIn("go",data["labels"])
            self.assertNotIn("needs-human",data["labels"]);self.assertEqual(data["comments"],before)

    def test_owner_reconcilers_are_locally_serialized(self):
        import threading
        from unittest import mock
        from memory_adapter import MemoryTicket
        data=issue("#1",held=True,labels=["ready-for-human","go"])
        a=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[data]);a.fail_at=1
        with self.assertRaises(RuntimeError):a.load()[0].mark_needs_human("failed","detail")
        rec=a.load()[0].park_intent
        second=MemoryTracker(a.root,P.GITHUB,[data])
        entered,release=threading.Event(),threading.Event()
        original=MemoryTicket._release;results=[];errors=[]
        def gated(t,*args,**kwargs):
            entered.set()
            if not release.wait(2):raise RuntimeError("test timeout")
            return original(t,*args,**kwargs)
        def run(tr):
            try:results.append(tr.complete_park(tr.load()[0],rec))
            except Exception as e:errors.append(e)
        with mock.patch.object(MemoryTicket,"_release",gated):
            one=threading.Thread(target=run,args=(a,));one.start()
            self.assertTrue(entered.wait(2))
            two=threading.Thread(target=run,args=(second,));two.start()
            release.set();one.join(3);two.join(3)
            self.assertFalse(one.is_alive() or two.is_alive())
        self.assertFalse(errors);self.assertEqual(sorted(results),[False,True])
        self.assertEqual(sum(c["body"].startswith(P.marked("Park complete:")) for c in data["comments"]),1)

    def test_missing_or_foreign_authority_blocks_every_public_write(self):
        for designation in (None, "ambiguous", "f" * 32):
            data=issue("#1",held=True,labels=["ready-for-human","go"])
            tr=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[data])
            tr.c["park_authority"]=designation
            t=tr.load()[0]
            for call in (lambda:t.mark_needs_human("failed","detail"),
                         lambda:t.mark_claimed("branch","writer"), lambda:t.mark_ready("retry"),
                         lambda:t.approve("go"), lambda:t.enable(), lambda:t.decline("drop"),
                         lambda:t.post_packet("packet"), lambda:tr.create("fix","body",[])):
                with self.assertRaises(RuntimeError):call()
            self.assertEqual(tr.writes,0)

    def test_unpublished_local_intent_blocks_claim_and_resumes_same_operation(self):
        data=issue("#1",held=True,labels=["ready-for-human","go"])
        tr=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[data]);tr.fail_at=0
        with self.assertRaises(RuntimeError):tr.load()[0].mark_needs_human("first","detail")
        rec=tr._pending()["#1"]
        with self.assertRaises(RuntimeError):tr.load()[0].mark_claimed("new","writer")
        with self.assertRaises(RuntimeError):tr.load()[0].approve("premature")
        tr.load()[0].mark_needs_human("replacement","wrong")
        intents=[c["body"] for c in data["comments"] if c["body"].startswith(P.marked("Park intent:"))]
        self.assertEqual(len(intents),1);self.assertIn(rec["op"],intents[0])
        self.assertIn("detail",tr.load()[0].packet);self.assertNotIn("wrong",tr.load()[0].packet)

    def test_corrupt_local_journal_and_legacy_intent_fail_closed(self):
        for contents in ("broken", "[]", '{"#1": null}'):
            tr=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[issue("#1")])
            tr._pending_path().write_text(contents)
            with self.assertRaisesRegex(RuntimeError,"journal"):
                tr.load()[0].mark_needs_human("failed","detail")
            self.assertEqual(tr.writes,0)
        tr=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[issue("#1")])
        tr._pending_save({"#1":{"comment":"legacy"}})
        with self.assertRaisesRegex(RuntimeError,"legacy|ambiguous"):tr.finish_parks()
        self.assertEqual(tr.writes,0)

    def test_nonwriter_tick_and_finish_wait_before_any_model_call(self):
        from unittest import mock
        tr=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[issue("#1")])
        tr.c.pop("park_authority")
        with mock.patch.object(runway,"run_agent",side_effect=AssertionError("model must not run")):
            self.assertFalse(runway.tick(runway.DEFAULT_CONFIG,tr.root,tr))
            self.assertFalse(runway.finish(runway.DEFAULT_CONFIG,tr.root,tr,force=True))
        self.assertEqual(tr.writes,0)

    def test_foreign_creation_cannot_replace_unfinished_intent(self):
        for rules in (P.GITHUB,P.LINEAR):
            data=issue("#1",held=True,labels=["ready-for-human","go"])
            a=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data]);a.fail_at=1
            with self.assertRaises(RuntimeError):a.load()[0].mark_needs_human("first","detail")
            rec=a.load()[0].park_intent
            b=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data])
            # Even incorrectly assigning B authority cannot overwrite A's unfinished operation.
            b.c["park_authority"]=b.park_owner()
            with self.assertRaisesRegex(RuntimeError,"foreign"):
                b.load()[0].mark_needs_human("replacement","wrong")
            self.assertEqual(b.writes,0);self.assertEqual(a.load()[0].park_intent,rec)

    def test_creation_waits_for_local_reconciliation_then_refuses_replacement(self):
        import threading
        from unittest import mock
        from memory_adapter import MemoryTicket
        data=issue("#1",held=True,labels=["ready-for-human","go"])
        a=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[data]);a.fail_at=1
        with self.assertRaises(RuntimeError):a.load()[0].mark_needs_human("first","detail")
        rec=a.load()[0].park_intent
        second=MemoryTracker(a.root,P.GITHUB,[data])
        entered,release,started=threading.Event(),threading.Event(),threading.Event()
        original=MemoryTicket._release;errors=[]
        def gated(t,*args,**kwargs):
            entered.set()
            if not release.wait(2):raise RuntimeError("test timeout")
            return original(t,*args,**kwargs)
        def create():
            started.set()
            try:second.load()[0].mark_needs_human("replacement","wrong")
            except RuntimeError as e:errors.append(str(e))
        with mock.patch.object(MemoryTicket,"_release",gated):
            one=threading.Thread(target=lambda:a.complete_park(a.load()[0],rec));one.start()
            self.assertTrue(entered.wait(2))
            two=threading.Thread(target=create);two.start();self.assertTrue(started.wait(2))
            release.set();one.join(3);two.join(3)
            self.assertFalse(one.is_alive() or two.is_alive())
        self.assertEqual(len(errors),1)
        self.assertEqual(sum(c["body"].startswith(P.marked("Park intent:")) for c in data["comments"]),1)

    def test_stale_claim_cannot_park_new_claim(self):
        data=issue("#1",labels=["ready-for-agent"])
        a=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[data])
        a.load()[0].mark_claimed("old","writer")
        stale=a.load()[0]
        a.now="2026-12-02T00:00:00Z"
        a.load()[0].mark_ready("retry")
        a.load()[0].mark_claimed("new","writer")
        before=a.writes
        with self.assertRaisesRegex(RuntimeError,"stale claim"):
            stale.mark_needs_human("delayed","wrong")
        self.assertEqual(a.writes,before);self.assertTrue(data["held"])

    def test_unrelated_completion_cannot_clear_pending_operation(self):
        data=issue("#1",held=True,labels=["ready-for-human","go"])
        a=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[data]);a.fail_at=1
        with self.assertRaises(RuntimeError):a.load()[0].mark_needs_human("failed","detail")
        data["comments"].append({"body":P.marked("Park complete: " + "f"*32), "createdAt":"2026-10-20T00:00:00Z", "trusted":True,"who":"runway","assoc":"OWNER"})
        b=MemoryTracker(Path(tempfile.mkdtemp()),P.GITHUB,[data])
        self.assertIsNotNone(b.load()[0].park_intent)
        self.assertEqual(b.load()[0].gate,"none")

    def test_go_during_pending_park_is_not_consumed(self):
        for rules in (P.GITHUB,P.LINEAR):
            data=issue('#1',held=True,labels=['ready-for-human','go'])
            a=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data]);a.fail_at=2
            with self.assertRaises(RuntimeError):a.load()[0].mark_needs_human('failed','detail')
            data['comments'].append({'body':'go premature','createdAt':'2026-10-20T00:00:00Z','trusted':True,'who':'Joe','assoc':'OWNER'})
            b=MemoryTracker(Path(tempfile.mkdtemp()),rules,[data]);b.now='2026-10-21T00:00:00Z'
            with contextlib.redirect_stdout(io.StringIO()):b.sync()
            self.assertEqual(b.load()[0].status,'needs-human');self.assertNotIn('go',b.load()[0].labels)


if __name__=='__main__':unittest.main()
