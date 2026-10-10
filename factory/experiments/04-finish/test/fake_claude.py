#!/usr/bin/env python3
"""Stand-in for `claude -p --output-format json`. Tells the call apart by its prompt,
does a little fake work, and prints Claude Code's JSON result shape with a session id."""
import json, pathlib, re, sys, uuid
prompt = sys.stdin.read()
sid = str(uuid.uuid4())
if prompt.startswith("You are preparing a decision"):
    out = "### Decision needed\nUse greet()?\n### Options\n- greet() (recommended)\n- hello()"
elif prompt.startswith("You are reviewing"):
    head = re.search(r"head under review is ([0-9a-f]{40})", prompt).group(1)
    out = f"Reviewed: {head}\n- greeting.txt:1 says 'helo', a typo the tickets didn't ask for."
elif prompt.startswith("Fix these review findings"):
    p = pathlib.Path("greeting.txt"); p.write_text(p.read_text().replace("helo", "hello"))
    out = "fixed the typo"
elif prompt.startswith("Write the pull request body"):
    out = "## Summary\n\n```\ngreeting.txt  (new)\nexport.txt    (new)\n```\n\n## Evidence\n\nCheck exited 0.\n\n## Merge danger\n\nTwo-way door. Blast radius: none outside this demo."
else:  # a ticket run
    title = re.search(r"^#\s+(.+)$", prompt, re.M).group(1)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if title == "Greeting module":
        pathlib.Path("greeting.txt").write_text("helo\n")
    # "Export" fails its first attempt: the check wants the word ok in it.
    retry = "previous attempt failed" in prompt
    pathlib.Path(f"{slug}.txt").write_text("ok\n" if title != "Export" or retry else "broken\n")
    out = f"did {title}"
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": out,
                  "session_id": sid, "num_turns": 3, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 1000, "output_tokens": 200,
                            "cache_read_input_tokens": 500, "cache_creation_input_tokens": 0}}))
# Leave a transcript where Claude Code would, so `runway retro` can find it.
import os
home = pathlib.Path(os.environ["CLAUDE_CONFIG_DIR"])
d = home / "projects" / re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
d.mkdir(parents=True, exist_ok=True)
(d / f"{sid}.jsonl").write_text("{}\n")
