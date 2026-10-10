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
                        with contextlib.redirect_stdout(io.StringIO()):b.sync()
                        self.assertEqual(b.load()[0].gate,'approved');self.assertEqual(b.load()[0].status,'ready')

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
