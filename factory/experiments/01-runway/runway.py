#!/usr/bin/env python3
"""Pointer: the Runway engine moved to pm/runway/runway.py (2026-10-09; was factory/plugin/runway/).

Kept so LaunchAgents and notes that name this path keep working. Edit the engine there, not here.
"""
import runpy
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[3] / "pm" / "runway" / "runway.py"
sys.path.insert(0, str(ENGINE.parent))
sys.argv[0] = str(ENGINE)
runpy.run_path(str(ENGINE), run_name="__main__")
