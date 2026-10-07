#!/usr/bin/env python3
"""Stand-in for `claude -p`: reads the prompt, writes a file, so the loop can be tested offline."""
import re, sys, pathlib
prompt = sys.stdin.read()
title = re.search(r"^#\s+(.+)$", prompt, re.M).group(1)
slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
notes = "\n".join(l for l in prompt.splitlines() if l.lower().startswith("go "))
pathlib.Path(f"{slug}.txt").write_text(f"work for: {title}\n{notes}\n")
print(f"fake agent did: {title}")
