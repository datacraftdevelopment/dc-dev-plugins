"""Offline tests for decisions on GitHub: the packet, go by comment or label, drop, a stranger's go, and
`runway go` / `runway no`. Same stateful fake `gh` as the write tests. Run: python3 -m pytest -q test_github_decisions.py"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_github_tracker import issue  # noqa: E402
from test_github_write import GitHubWrites  # noqa: E402

PACKET = "\U0001f6eb runway · **Decision packet**\n\nShall I?"


def labels(s):
    return {l["name"] for l in s["labels"]["nodes"]}


class GitHubDecisions(GitHubWrites):
    def parked(self, *comments, extra_labels=()):
        """A ready-for-human issue holding Runway's packet, then the given (body, association) comments."""
        return issue(1, labels=("ready-for-human", "needs-human", *extra_labels),
                     comments=[(PACKET, "OWNER"), *comments])

    def test_post_packet_comments_and_parks(self):
        self.data(issue(1, labels=("ready-for-human",)))
        self.ticket().post_packet("Shall I?")
        s = self.stored()
        self.assertIn("needs-human", labels(s))
        body = self.comments()[-1]
        self.assertTrue(body.startswith("\U0001f6eb runway · "))
        self.assertIn("Shall I?", body)
        self.assertIn("`go`", body)
        self.assertIn("`drop`", body)
        t = self.ticket()
        self.assertEqual((t.status, t.gate), ("needs-human", "human"))
        self.assertIn("Shall I?", t.packet)

    def test_go_comment_approves_and_the_note_reaches_the_agent(self):
        self.data(self.parked(("go, but keep it to one file", "OWNER")))
        self.tracker().sync()
        s = self.stored()
        self.assertEqual(labels(s), {"ready-for-human", "go"})
        self.assertEqual(self.comments()[-1], "\U0001f6eb runway · Approved. but keep it to one file")
        t = self.ticket()
        self.assertEqual((t.status, t.gate), ("ready", "approved"))
        self.assertIn("go, but keep it to one file", t.text)
        self.assertEqual(t.joe_replies(), [])  # answered once; the next sync does nothing
        n = len(self.comments())
        self.tracker().sync()
        self.assertEqual(len(self.comments()), n)

    def test_go_label_approves(self):
        self.data(self.parked(extra_labels=("go",)))
        self.tracker().sync()
        s = self.stored()
        self.assertEqual(labels(s), {"ready-for-human", "go"})
        self.assertEqual(self.comments()[-1], "\U0001f6eb runway · Approved.")
        self.assertEqual(self.ticket().status, "ready")

    def test_drop_closes_as_not_planned(self):
        self.data(self.parked(("drop", "OWNER")))
        self.tracker().sync()
        s = self.stored()
        self.assertEqual((s["state"], s["stateReason"]), ("CLOSED", "NOT_PLANNED"))
        self.assertIn("Dropped.", self.comments()[-1])
        self.assertEqual(self.ticket().status, "resolved")

    def test_members_and_collaborators_count(self):
        for who in ("MEMBER", "COLLABORATOR"):
            self.data(self.parked(("go", who)))
            self.tracker().sync()
            self.assertIn("go", labels(self.stored()), who)

    def test_a_strangers_go_is_ignored_and_logged_once(self):
        for who in ("NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR"):
            self.data(self.parked(("go", who)))
            self.tracker().sync()
            s = self.stored()
            self.assertEqual(labels(s), {"ready-for-human", "needs-human"}, who)
            self.assertEqual(len(self.comments()), 2, who)  # the packet and the stranger's; Runway added none
            self.assertEqual(self.ticket().status, "needs-human")
        log = (self.dir / "_pm" / "runway.log").read_text()
        self.assertEqual(log.count("#1 ignored 'go' from unknown (NONE)"), 1)
        self.tracker().sync()  # a later tick sees the same comment: still one line
        self.assertEqual((self.dir / "_pm" / "runway.log").read_text(), log)

    def test_a_strangers_drop_is_ignored(self):
        self.data(self.parked(("drop", "NONE")))
        self.tracker().sync()
        self.assertEqual(self.stored()["state"], "OPEN")

    def test_a_stranger_cannot_override_joe(self):
        self.data(self.parked(("hold on, thinking", "OWNER"), ("go", "NONE")))
        self.tracker().sync()
        self.assertNotIn("go", labels(self.stored()))

    def test_runways_own_comments_are_never_joes(self):
        # The packet itself says "go" and "drop"; it must not approve or drop anything.
        self.data(self.parked())
        self.tracker().sync()
        s = self.stored()
        self.assertEqual((s["state"], labels(s)), ("OPEN", {"ready-for-human", "needs-human"}))
        self.assertEqual(self.ticket().joe_replies(), [])

    def test_a_no_comment_stays_parked(self):
        self.data(self.parked(("not now", "OWNER")))
        self.tracker().sync()
        self.assertEqual(self.ticket().status, "needs-human")

    def test_ready_issues_are_left_alone(self):
        self.data(issue(1, labels=("ready-for-human",), comments=[("go", "OWNER")]))
        self.tracker().sync()
        self.assertEqual(self.comments(), ["go"])

    # -- the command line --

    def test_runway_go_and_no_on_a_github_ticket(self):
        self.data(self.parked())
        runway.cmd_answer(self.dir, self.tracker(), "1", True, "ship it")
        self.assertEqual(self.ticket().gate, "approved")
        self.assertEqual(self.comments()[-1], "\U0001f6eb runway · Approved. ship it")
        self.data(self.parked())
        runway.cmd_answer(self.dir, self.tracker(), "#1", False, "drop")
        self.assertEqual(self.stored()["stateReason"], "NOT_PLANNED")
        self.data(self.parked())
        runway.cmd_answer(self.dir, self.tracker(), "#1", False, "too risky")
        self.assertEqual(self.comments()[-1], "\U0001f6eb runway · Joe said no: too risky")
        self.assertEqual(self.stored()["state"], "OPEN")


if __name__ == "__main__":
    unittest.main()
