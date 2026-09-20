#!/usr/bin/env python3
"""Run from the worktree root. Checks the cross-check report's contract: every finding quotes text that
really is at the cited line of the cited doc, and cites a rules source that exists. Not whether a finding is right."""
import re, sys
from pathlib import Path
root = Path.cwd()
report = root / "docs/reviews/2026-09-20-rules-docs-crosscheck.md"
if not report.exists():
    sys.exit(f"FAIL: {report} not written")
text = report.read_text()
fails = []
for heading in ["## Summary", "## Findings", "## Checked and correct", "## Not checked"]:
    if heading.lower() not in text.lower():
        fails.append(f"missing section {heading!r}")
findings = re.findall(r"^### .+$", text, re.M)
blocks = re.split(r"^### .+$", text, flags=re.M)[1:]
for title, block in zip(findings, blocks):
    doc = re.search(r"\*\*Doc:\*\*\s*`(docs/[^`:]+):(\d+)`", block)
    quote = re.search(r"\*\*Says:\*\*\s*\"(.+?)\"", block, re.S)
    source = re.search(r"\*\*Rule source:\*\*\s*`([^`:]+)(?::(\d+))?`", block)
    if not (doc and quote and source):
        fails.append(f"{title}: needs **Doc:** `docs/file.md:LINE`, **Says:** \"quote\", **Rule source:** `path[:LINE]`")
        continue
    path = root / doc.group(1)
    if not path.exists():
        fails.append(f"{title}: {doc.group(1)} does not exist"); continue
    lines = path.read_text().splitlines()
    n = int(doc.group(2))
    window = " ".join(lines[max(0, n - 3): n + 2])
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    if norm(quote.group(1))[:60] not in norm(window):
        fails.append(f"{title}: the quoted text is not at {doc.group(1)}:{n}")
    if not (root / source.group(1)).exists():
        fails.append(f"{title}: rule source {source.group(1)} does not exist")
    for field in ["**Rule says:**", "**Fix:**"]:
        if field not in block:
            fails.append(f"{title}: missing {field}")
checked = text.lower().split("## checked and correct")[-1].split("\n## ")[0]
cites = re.findall(r"`docs/[^`:]+:\d+`", checked)
if len(cites) < 8:
    fails.append(f"'Checked and correct' cites {len(cites)} doc lines; show at least 8 rules statements you verified, each with `docs/file.md:LINE`")
for f in fails:
    print("FAIL:", f)
print(f"verify_crosscheck: {len(findings)} finding(s);", "passed" if not fails else f"{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
