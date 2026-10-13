#!/usr/bin/env python3
"""A small evaluation of the supplemental bug check on this repo's own history (gh-90). Not collected by pytest.

    python3 pm/runway/test/eval_bug_check.py [--cases id,id] [--cmd "<checker command>"] [--out results.md]

Each bug case is a past review fix undone: the reviewer sees the fixed file going back to its buggy version, and a
finding on that file is a catch. Each clean case is a fix applied forward (code a review asked for and accepted):
any finding is a false positive. Every case runs `runway.bug_check` in a throwaway worktree with the same
settings as finish (the configured cmd, Haiku by default), so it costs one checker call per case.
It prints a Markdown table of catches, misses and false positives, and the reported usage."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
CASES = [
    # id, kind, commit, path, what the fix was
    ("bug-linear-claim", "bug", "7763d7d", "factory/plugin/runway/linear_tracker.py",
     "a parked or retried ticket still reads as claimed by its old stamp"),
    ("bug-stop-now", "bug", "7763d7d", "factory/plugin/runway/runway.py",
     "pause --stop-now stops only the heartbeat's agent, not every live one"),
    ("bug-resume-race", "bug", "f8f5f78", "pm/runway/runway.py",
     "resume --if-reason can delete a pause written meanwhile; signin checks only the default harness"),
    ("clean-check-shim", "clean", "f8f5f78", "factory/scripts/check.sh", "PYTHON reaches child scripts via a shim"),
    ("clean-chores-why", "clean", "e78b345", "pm/runway/chores.json", "a chore's why names what it rewrites"),
]


def git(*a, cwd=REPO, check=True, stdin=None):
    return subprocess.run(["git", *a], cwd=cwd, check=check, capture_output=True, text=True, input=stdin)


def snapshot(case, wt: Path) -> str:
    """Build the case in wt (detached). Returns the base sha the reviewer diffs against."""
    cid, kind, commit, path, _ = case
    patch = git("diff", f"{commit}^", commit, "--", path).stdout
    start = commit if kind == "bug" else f"{commit}^"
    git("worktree", "add", "-q", "--detach", str(wt), start)
    git("apply", *(["-R"] if kind == "bug" else []), "-", cwd=wt, stdin=patch)
    git("-c", "user.name=eval", "-c", "user.email=eval@example.com", "commit", "-qam", f"eval {cid}", cwd=wt)
    return git("rev-parse", start).stdout.strip()


def run_case(case, cmd: str | None, home: Path) -> dict:
    cid, kind, commit, path, what = case
    wt = home / cid
    base = snapshot(case, wt)
    bc = {"mode": "optional", **({"cmd": cmd} if cmd else {})}
    cfg = dict(runway.DEFAULT_CONFIG, base_branch=base, bug_check=bc)
    try:
        res = runway.bug_check(cfg, home, wt, [])
    finally:
        git("worktree", "remove", "--force", str(wt), check=False)
    on_file = [f for f in res["findings"] if f["file"].lstrip("./") == path]
    if res["status"] not in runway.BUG_CHECK_DONE:
        score = "incomplete"
    elif kind == "bug":
        score = "catch" if on_file else "miss"
    else:
        score = "false positive" if res["findings"] else "clean"
    return {"id": cid, "kind": kind, "commit": commit, "path": path, "what": what, "status": res["status"],
            "detail": res["detail"], "score": score, "findings": res["findings"], "tokens": res["tokens"],
            "cost_usd": res["cost_usd"], "secs": res["secs"]}


def table(rows: list) -> str:
    out = ["| case | kind | outcome | score | findings | tokens | cost |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        tok = "not reported" if r["tokens"] is None else str(r["tokens"])
        cost = "not reported" if r["cost_usd"] is None else f"${r['cost_usd']:.4f}"
        out.append(f"| {r['id']} | {r['kind']} | {r['status']} | {r['score']} | {len(r['findings'])} | {tok} | {cost} |")
    n = lambda s: sum(1 for r in rows if r["score"] == s)
    out.append("")
    out.append(f"Catches {n('catch')}, misses {n('miss')}, false positives {n('false positive')}, "
               f"clean {n('clean')}, incomplete {n('incomplete')}.")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--cmd", help="checker command (default: bug_check's, Haiku)")
    ap.add_argument("--out", type=Path, help="also write the table and findings here")
    a = ap.parse_args()
    pick = set(a.cases.split(",")) if a.cases else None
    home = Path(tempfile.mkdtemp(prefix="runway-bug-eval-"))
    os.environ.setdefault("RUNWAY_HOME", str(home / "runway-home"))
    rows = [run_case(c, a.cmd, home) for c in CASES if pick is None or c[0] in pick]
    text = table(rows)
    print(text)
    if a.out:
        a.out.write_text(text + "\n```json\n" + json.dumps(rows, indent=1) + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
