"""factory/scripts/check.sh: a missing pytest stops it plainly, and PYTHON (absolute or relative) reaches the
suites' own `python3` calls. Runs the script against a throwaway tree with one tiny test."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The chosen interpreter is a wrapper that logs each call, so the probe can tell it from PATH's own python3.
PROBE = '''import os, subprocess
from pathlib import Path
def test_child_python3_is_the_chosen_one():
    mark = Path(os.environ["MARK"])
    before = len(mark.read_text().splitlines())
    subprocess.run(["python3", "-c", "pass"], check=True)
    assert len(mark.read_text().splitlines()) == before + 1
'''


class CheckScript(unittest.TestCase):
    def tree(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "factory").mkdir()
        shutil.copytree(ROOT / "factory/scripts", d / "factory/scripts")
        (d / "tests").mkdir()
        (d / "tests/test_probe.py").write_text(PROBE)
        (d / "v/bin").mkdir(parents=True)
        wrapper = d / "v/bin/python3"
        wrapper.write_text(f'#!/bin/sh\necho call >> "$MARK"\nexec "{sys.executable}" "$@"\n')
        wrapper.chmod(0o755)
        (d / "mark").write_text("")
        return d

    def run_check(self, d, python):
        env = {**os.environ, "PYTHON": python, "MARK": str(d / "mark")}
        return subprocess.run(["bash", "factory/scripts/check.sh"], cwd=d, env=env, capture_output=True, text=True)

    def test_relative_python_reaches_child_python3(self):
        r = self.run_check(self.tree(), "v/bin/python3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_absolute_python_reaches_child_python3(self):
        d = self.tree()
        r = self.run_check(d, str(d / "v/bin/python3"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_an_interpreter_without_pytest_stops_with_a_plain_message(self):
        r = self.run_check(self.tree(), "/nonexistent/python3")
        self.assertEqual(r.returncode, 2)
        self.assertIn("has no pytest", r.stderr)


if __name__ == "__main__":
    unittest.main()
