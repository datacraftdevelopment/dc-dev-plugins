"""The experiment shell tests must ignore this Mac's real ~/.runway (DAT-45).

A machine-wide pause (or quiet-time rules, or an agent registry) in the outer RUNWAY_HOME
must not change what these suites see. We point the outer RUNWAY_HOME at a temp dir holding
an active pause and run each suite; a suite that read it would log "paused until" and fail.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SUITES = [
    "factory/experiments/03-linear/test/test_linear.sh",
    "factory/experiments/04-finish/test/test_finish.sh",
]


@pytest.mark.parametrize("suite", SUITES)
def test_suite_ignores_outer_pause(suite, tmp_path):
    home = tmp_path / "outer-runway"
    home.mkdir()
    (home / "pause").write_text(json.dumps(
        {"until": "2099-01-01T00:00:00+00:00", "mode": "finish", "at": None}))
    env = {**os.environ, "RUNWAY_HOME": str(home)}
    r = subprocess.run(["bash", str(ROOT / suite)], env=env, capture_output=True,
                       text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    assert "paused until" not in r.stdout + r.stderr
