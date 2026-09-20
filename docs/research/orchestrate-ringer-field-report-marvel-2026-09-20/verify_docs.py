#!/usr/bin/env python3
"""Run from the worktree root. Checks the README rewrite and the corrected power-set caveat."""
import re, sys
from pathlib import Path
root = Path.cwd()
fails = []
readme = (root / "apps/marvel/README.md").read_text()
for banned in ["create-next-app", "yarn dev", "bun dev", "Deploy on Vercel", "Geist"]:
    if banned.lower() in readme.lower():
        fails.append(f"README still has create-next-app boilerplate: {banned!r}")
for needed in ["npm test", "NEXT_PUBLIC_CONVEX_URL", "CONVEX_AGENT_MODE=anonymous", "/campaigns", "/characters/[id]/sheet", "evaluateCharacter", "marvel-convex", "no login"]:
    if needed.lower() not in readme.lower():
        fails.append(f"README never mentions {needed!r}")
if len(readme.split()) < 250:
    fails.append(f"README is only {len(readme.split())} words; it should orient a new developer")
for path in set(re.findall(r"`((?:src|convex)/[A-Za-z0-9_./\[\]-]+)`", readme)):
    if not (root / "apps/marvel" / path).exists():
        fails.append(f"README names `{path}`, which does not exist under apps/marvel")
if "—" in readme:
    fails.append("README uses an em dash; the project's writing rules forbid them")
rules = (root / "context/power-sets-rules.md").read_text()
if "does NOT encode" in rules or "never trust the flag" in rules:
    fails.append("context/power-sets-rules.md still carries the stale caveat wording")
if "player_selectable" not in rules:
    fails.append("context/power-sets-rules.md should still explain the player_selectable flag, corrected")
if not re.search(r"player_selectable\W{0,4}=?\W{0,4}0|flagged\s+0|not selectable", rules):
    fails.append("the corrected caveat should say the four parent sets are flagged player_selectable = 0")
for f in fails:
    print("FAIL:", f)
print("verify_docs:", "passed" if not fails else f"{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
