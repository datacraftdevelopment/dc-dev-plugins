"""Offline tests: tickets name their spec file, and the prompts point workers and reviewers at it.
Run: python3 -m pytest -q test_ticket_specs.py"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402


def ticket(text):
    return SimpleNamespace(text=text)


class TicketSpecs(unittest.TestCase):
    def test_reads_spec_header_lines(self):
        a = ticket("# T\n\nBlocked by: #7\n\nPart of #46.\nSpec: docs/specs/queue-plan.md\n\nBody")
        b = ticket("# U\n\nspec: `docs/specs/queue-plan.md`\n")
        c = ticket("# V\n\nSpec: docs/specs/review-gate.md\n")
        self.assertEqual(runway.ticket_specs([a, b, c]), ["docs/specs/queue-plan.md", "docs/specs/review-gate.md"])

    def test_ignores_tickets_without_a_spec_file(self):
        self.assertEqual(runway.ticket_specs([ticket("# T\n\nThe spec says so.\nSpec: #46\n"), SimpleNamespace()]), [])

    def test_prompts_point_at_the_spec_file(self):
        self.assertIn("`Spec:` line naming a file", runway.RUN_PROMPT)
        self.assertIn("gh issue view", runway.RUN_PROMPT)
        self.assertIn("`Spec:` line", runway.PREP_PROMPT)
        runway.RUN_PROMPT.format(path="p", ticket="t", extra="")
        runway.PREP_PROMPT.format(path="p", ticket="t")


if __name__ == "__main__":
    unittest.main()
