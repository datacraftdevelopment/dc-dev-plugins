"""Offline test: RUN_PROMPT tells a headless run where /tdd's seams come from.
Run: python3 -m pytest -q test_run_prompt.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402


class RunPromptSeams(unittest.TestCase):
    def setUp(self):
        self.text = " ".join(runway.RUN_PROMPT.split())

    def test_seams_come_from_ticket_or_spec(self):
        self.assertIn("the ticket or its spec names", self.text)

    def test_fallback_is_existing_public_interface(self):
        self.assertIn("existing public interface of the module being changed", self.text)

    def test_no_stopping_to_confirm_seams(self):
        self.assertIn("Don't stop to confirm seams", self.text)

    def test_only_new_module_or_changed_interface_asks(self):
        self.assertIn("new module or a changed public interface", self.text)

    def test_prompt_still_formats(self):
        out = runway.RUN_PROMPT.format(path="p", ticket="t", extra="")
        self.assertIn("Ticket (p):", out)


if __name__ == "__main__":
    unittest.main()
