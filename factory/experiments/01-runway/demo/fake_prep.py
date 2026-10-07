#!/usr/bin/env python3
"""Stand-in for the read-only prep agent: prints a decision packet."""
import re, sys
title = re.search(r"^#\s+(.+)$", sys.stdin.read(), re.M).group(1)
print(f"""### Decision needed
Approve the plan for "{title}"?
### Options
- **go (recommended)**: agent implements option A as planned.
- no: park it; nothing changes.
### What the agent will do on "go"
Add one module and a test; checked by the repo check command.
### Risks / one-way doors
none
### Context Joe needs
- This is a demo packet from fake_prep.py.""")
