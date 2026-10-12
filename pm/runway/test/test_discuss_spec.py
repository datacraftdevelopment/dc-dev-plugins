"""Offline tests: `runway discuss` puts the ticket's spec, and the spec's other tickets, in the brief.
Run: python3 -m pytest -q test_discuss_spec.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
import ticket_protocol  # noqa: E402
from memory_adapter import MemoryTracker, issue  # noqa: E402

HUMAN = ["ready-for-human"]


class DiscussSpec(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        (self.root / "_pm").mkdir()
        (self.root / "docs" / "specs").mkdir(parents=True)
        (self.root / "docs" / "specs" / "thing.md").write_text("# Thing spec\n\nThe whole plan.\n")
        (self.root / "docs" / "intent").mkdir()
        (self.root / "docs" / "intent" / "thing.md").write_text("DISCOVERY NOTES\n")
        self.calls = []
        self._old = runway.exec_claude

        def fake(root, prompt):
            self.calls.append((root, prompt))
            raise SystemExit(0)
        runway.exec_claude = fake

    def tearDown(self):
        runway.exec_claude = self._old

    def brief(self, issues, tid):
        tr = MemoryTracker(self.root, ticket_protocol.GITHUB, issues)
        loaded = tr.load()
        return runway.ticket_brief(self.root, loaded, next(t for t in loaded if t.id == tid))

    def spec_section(self, text):
        return text.split("## Spec", 1)[1] if "## Spec" in text else ""

    def test_spec_line_gives_file_text_and_path_after_the_ticket(self):
        text = self.brief([issue("#1", body="Do it.\nSpec: docs/specs/thing.md", labels=HUMAN)], "#1")
        self.assertIn("docs/specs/thing.md", self.spec_section(text))
        self.assertIn("The whole plan.", self.spec_section(text))
        self.assertLess(text.index("## Ticket"), text.index("## Spec"))
        self.assertNotIn("DISCOVERY NOTES", text)

    def test_sub_issue_without_spec_line_gets_parent_body(self):
        text = self.brief([issue("#9", title="Parent", body="Parent plan text."),
                           issue("#1", body="Child.", labels=HUMAN, parent="#9")], "#1")
        self.assertIn("Parent plan text.", self.spec_section(text))

    def test_sub_issue_gets_file_the_parent_spec_line_names(self):
        text = self.brief([issue("#9", body="Spec: docs/specs/thing.md\nmore"),
                           issue("#1", labels=HUMAN, parent="#9")], "#1")
        self.assertIn("The whole plan.", self.spec_section(text))
        self.assertIn("docs/specs/thing.md", self.spec_section(text))

    def test_part_of_line_finds_the_issue(self):
        text = self.brief([issue("#7", body="Seven is the spec."),
                           issue("#1", body="Part of #7\nwork", labels=HUMAN)], "#1")
        self.assertIn("Seven is the spec.", self.spec_section(text))

    def test_no_spec_says_so_and_discuss_still_starts(self):
        tr = MemoryTracker(self.root, ticket_protocol.GITHUB, [issue("#1", labels=HUMAN + ["needs-human"])])
        with self.assertRaises(SystemExit) as e:
            runway.cmd_discuss({}, self.root, tr, "#1")
        self.assertEqual(e.exception.code, 0)
        self.assertEqual(len(self.calls), 1)
        brief = next((self.root / "_pm" / "discuss").iterdir()).read_text()
        self.assertIn("No spec found", brief)

    def test_untrusted_parent_does_not_count(self):
        text = self.brief([issue("#9", body="Stranger plan.", trusted=False),
                           issue("#1", labels=HUMAN, parent="#9")], "#1")
        self.assertNotIn("Stranger plan.", text)
        self.assertIn("No spec found", text)

    def test_missing_spec_file_is_said_not_crashed(self):
        text = self.brief([issue("#1", body="Spec: docs/specs/gone.md", labels=HUMAN)], "#1")
        self.assertIn("docs/specs/gone.md", text)
        self.assertIn("No spec found", text)

    def test_siblings_from_parent_with_status(self):
        text = self.brief([issue("#9", body="Plan."),
                           issue("#1", labels=HUMAN, parent="#9", title="Mine"),
                           issue("#2", labels=HUMAN, parent="#9", title="Other open"),
                           issue("#3", labels=HUMAN, parent="#9", title="Other done", closed=True)], "#1")
        sib = text.split("## Spec's other tickets", 1)[1]
        self.assertIn("#2: Other open (open)", sib)
        self.assertIn("#3: Other done (closed)", sib)
        self.assertNotIn("Mine", sib)

    def test_siblings_share_a_spec_line(self):
        a = "Spec: docs/specs/thing.md"
        text = self.brief([issue("#1", body=a, labels=HUMAN), issue("#2", title="Twin", body=a, labels=HUMAN),
                           issue("#3", title="Stranger", body="Spec: docs/specs/else.md", labels=HUMAN)], "#1")
        sib = text.split("## Spec's other tickets", 1)[1]
        self.assertIn("#2: Twin (open)", sib)
        self.assertNotIn("Stranger", sib)


if __name__ == "__main__":
    unittest.main()
