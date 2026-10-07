#!/usr/bin/env python3
"""Pointer: the Runway engine moved to factory/plugin/runway/runway.py (2026-10-07).

Kept so LaunchAgents and notes that name this path keep working. Edit the engine there, not here.
"""
import runpy
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "plugin" / "runway" / "runway.py"
sys.path.insert(0, str(ENGINE.parent))
sys.argv[0] = str(ENGINE)
runpy.run_path(str(ENGINE), run_name="__main__")
