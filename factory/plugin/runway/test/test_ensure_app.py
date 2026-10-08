"""ensure_app opens the menu bar app only when it should. Run: python3 -m pytest -q test_ensure_app.py"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402


def done(code):
    return mock.Mock(returncode=code)


class EnsureAppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Path(self.tmp.name) / "Runway.app"
        self.app.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, env, pgrep_code=1, platform="darwin"):
        calls = []

        def fake(cmd, **_):
            calls.append(cmd[0])
            return done(pgrep_code if cmd[0] == "pgrep" else 0)

        with mock.patch.object(runway.subprocess, "run", side_effect=fake), mock.patch.object(runway.sys, "platform", platform):
            return runway.ensure_app(self.app, env=env), calls

    def test_opens_in_background_when_not_running(self):
        self.assertEqual(self.run_it({}), (True, ["pgrep", "open"]))

    def test_leaves_a_running_app_alone(self):
        self.assertEqual(self.run_it({}, pgrep_code=0), (False, ["pgrep"]))

    def test_skips_when_opted_out_under_tests_off_mac_or_not_installed(self):
        self.assertEqual(self.run_it({"RUNWAY_NO_APP": "1"}), (False, []))
        self.assertEqual(self.run_it({"PYTEST_CURRENT_TEST": "x"}), (False, []))
        self.assertEqual(self.run_it({}, platform="linux"), (False, []))
        self.app.rmdir()
        self.assertEqual(self.run_it({}), (False, []))


if __name__ == "__main__":
    unittest.main()
