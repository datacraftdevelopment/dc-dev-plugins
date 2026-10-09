"""Offline tests for sh(): a timeout bounds the whole attempt, grandchildren included.
Run: python3 -m pytest -q test_sh_timeout.py."""
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402

# Spawns a grandchild that keeps the inherited pipes open and ignores SIGTERM, writes its pid, then waits.
SPAWNER = (
    "import subprocess, sys, time\n"
    "g = subprocess.Popen([sys.executable, '-c', 'import signal, time; "
    "signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)'])\n"
    "open(sys.argv[1], 'w').write(str(g.pid))\n"
    "time.sleep(300)\n"
)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True).stdout.strip()
    return stat not in ("", "Z")  # a zombie still answers kill 0


class ShTimeout(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()).resolve()
        self.grace = getattr(runway, "KILL_GRACE_S", None)
        runway.KILL_GRACE_S = 1

    def tearDown(self):
        runway.KILL_GRACE_S = self.grace
        pidf = self.dir / "gpid"
        if pidf.exists():
            try:
                os.kill(int(pidf.read_text()), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass

    def test_grandchild_holding_pipes_cannot_outlive_the_timeout(self):
        pidf = self.dir / "gpid"
        t0 = time.time()
        with self.assertRaises(subprocess.TimeoutExpired):
            runway.sh([sys.executable, "-c", SPAWNER, str(pidf)], self.dir, timeout=2)
        self.assertLess(time.time() - t0, 2 + 2 * runway.KILL_GRACE_S + 3)
        time.sleep(0.3)
        self.assertFalse(alive(int(pidf.read_text())), "grandchild survived the timeout")

    def test_run_agent_turns_a_timeout_into_a_failed_attempt(self):
        (self.dir / "_pm").mkdir()
        cfg = dict(runway.DEFAULT_CONFIG, agent_timeout_s=1)
        pidf = self.dir / "gpid"
        r, _ = runway.run_agent(cfg, self.dir, [sys.executable, "-c", SPAWNER, str(pidf)], self.dir, "x", "T-1", "run")
        self.assertEqual(r.returncode, 124)
        self.assertIn("timed out", r.failure)
        self.assertFalse(r.auth)


if __name__ == "__main__":
    unittest.main()
