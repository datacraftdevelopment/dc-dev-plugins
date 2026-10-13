"""A stand-in bug checker for the eval test: reads the prompt on stdin and, in Claude's --output-format json,
reports one finding on the first file in the diff when that diff removes a line, else none. No model call."""
import json
import re
import sys

prompt = sys.stdin.read()
head = re.search(r"\(head ([0-9a-f]{40})\)", prompt).group(1)
diff = prompt.split('<untrusted name="diff">', 1)[1]
files = re.findall(r"^\+\+\+ b/(\S+)", diff, re.M)
removes = re.search(r"^-(?!--)", diff, re.M)
findings = [{"file": files[0], "line": 1, "category": "correctness", "scenario": "fixture: a guard was removed",
             "evidence": "fixture"}] if files and removes else []
print(json.dumps({"result": json.dumps({"reviewed": head, "findings": findings}), "session_id": "fake",
                  "num_turns": 1, "usage": {"input_tokens": 10, "output_tokens": 5}, "total_cost_usd": 0.0}))
