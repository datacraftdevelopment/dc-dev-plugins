"""Offline tests: tickets name their spec file, and the prompts point workers and reviewers at it.
Run: python3 -m pytest -q test_ticket_specs.py"""
import sys
import tempfile
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

    def test_prompts_carry_the_spec(self):
        self.assertIn("gh issue view", runway.RUN_PROMPT)
        run = runway.RUN_PROMPT.format(path="p", ticket="T", context="SPEC", extra="")
        prep = runway.PREP_PROMPT.format(path="p", ticket="T", context="SPEC")
        for prompt in (run, prep):
            self.assertLess(prompt.index("T"), prompt.index("SPEC"))


class SpecContext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "docs" / "specs").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_inlines_the_spec_and_names_its_notes(self):
        (self.base / "docs/specs/queue-plan.md").write_text("# Spec: queue plan\n\nThe plan is pure.\n")
        (self.base / "docs/specs/queue-plan.notes.md").write_text("ledger")
        out = runway.spec_context(self.base, ticket("Part of #46.\nSpec: docs/specs/queue-plan.md\n"))
        self.assertIn("## Spec: docs/specs/queue-plan.md", out)
        self.assertIn("The plan is pure.", out)
        self.assertIn("docs/specs/queue-plan.notes.md", out)
        self.assertNotIn("ledger", out)

    def test_missing_file_or_no_spec_gives_nothing(self):
        self.assertEqual(runway.spec_context(self.base, ticket("Spec: docs/specs/not-yet-on-main.md\n")), "")
        self.assertEqual(runway.spec_context(self.base, ticket("# T\n\nNo spec.\n")), "")

    def test_never_reads_outside_the_checkout(self):
        outside = self.base.parent / "secret-spec.md"
        outside.write_text("secret")
        try:
            self.assertEqual(runway.spec_context(self.base, ticket("Spec: ../secret-spec.md\n")), "")
        finally:
            outside.unlink()

    def test_cuts_a_huge_spec(self):
        (self.base / "docs/specs/big.md").write_text("x" * (runway.SPEC_CAP + 10))
        out = runway.spec_context(self.base, ticket("Spec: docs/specs/big.md\n"))
        self.assertIn("[cut at", out)
        self.assertLess(len(out), runway.SPEC_CAP + 300)


if __name__ == "__main__":
    unittest.main()
