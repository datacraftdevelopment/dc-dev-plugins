#!/usr/bin/env python3
"""Run Joe's two-seat adversarial review panel (codex + claude) through Ringer.

    python3 ringer_panel.py --repo <integration worktree> --base <base> --brief-file <file> --out <dir>

Fills the clone's panel kit (local/templates/adversarial-review-panel/manifest.template.json), runs
`ringer lint` then `ringer run`, copies each seat's report.md to <out>/review-codex.md and
<out>/review-claude.md, and prints {"seats": {"codex": {"status", "report"}, "claude": {...}}}.
Status is PASS, FAIL (a report exists but Ringer's check failed) or MISSING.

Exit 0 if at least one report exists, 1 if none does, 3 if Ringer is not found. Nothing inside the
Ringer clone is ever edited."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

SEATS = {"codex": "review-codex", "claude": "review-claude"}
SEAT_TIMEOUT_S = 1800
TEMPLATE = Path("local/templates/adversarial-review-panel/manifest.template.json")
FOCUS = ("Bugs, tickets that are missing or half done, and places where separately built tickets "
         "do not fit together.")


def find_ringer() -> tuple[list[str], Path] | None:
    """(command, clone root), or None. `ringer` on PATH, else RINGER_ROOT, else the default clone.
    The root is where the panel kit lives, so it is needed even when `ringer` is on PATH."""
    default = Path.home() / "Agentic-Mini/_Core/Ringer"
    configured = os.environ.get("RINGER_ROOT")
    candidates = [Path(configured).expanduser()] if configured else []
    on_path = shutil.which("ringer")
    if not configured:
        candidates.append(default)
        if on_path:
            candidates.append(Path(on_path).resolve().parent)
    root = next((c.resolve() for c in candidates if (c / "ringer.py").is_file() or
                 (c / TEMPLATE).is_file()), None)
    if on_path:
        cmd = [on_path]
    elif root and (root / "ringer.py").is_file():
        cmd = [sys.executable, str(root / "ringer.py")]
    else:
        return None
    if root is None or not (root / TEMPLATE).is_file():
        return None
    return cmd, root


def load_template(path: Path) -> dict:
    return json.loads(path.read_text())


def fill(node, values: dict):
    """Replace {{NAME}} in every string in one pass, so inserted text (the brief) is never rescanned."""
    if isinstance(node, str):
        return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), node)
    if isinstance(node, list):
        return [fill(n, values) for n in node]
    if isinstance(node, dict):
        return {k: fill(v, values) for k, v in node.items()}
    return node


def build_manifest(template: dict, repo: Path, base: str, brief: str, workdir: Path, kit_dir: Path,
                   slug: str = "runway-review") -> dict:
    manifest = fill(template, {
        "RUN_SLUG": slug,
        "WORKDIR": str(workdir),
        "REVIEW_SCOPE": f"the Runway integration branch ({base}...HEAD)",
        "ARTIFACT_PATH_OR_DIFF_COMMAND": f"git -C {repo} diff {base}...HEAD",
        "BRIEF": brief,
        "REVIEW_FOCUS": FOCUS,
        "KIT_DIR": str(kit_dir),
    })
    for task in manifest["tasks"]:
        task["timeout_s"] = SEAT_TIMEOUT_S
    return manifest


def seat_report(workdir: Path, key: str) -> Path | None:
    """The newest report.md under a folder named for the seat. Ringer's layout inside workdir is
    its own business, so look for it rather than assume a path."""
    found = [p for p in workdir.rglob("report.md") if key in p.relative_to(workdir).parts[:-1]]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def seat_passed(output: str, key: str, run_ok: bool) -> bool:
    """Did Ringer's check accept this seat? Read the seat's own line in Ringer's output; with none,
    fall back to whether the whole run exited 0."""
    for line in output.splitlines():
        if key in line:
            if re.search(r"\bFAIL", line, re.I):
                return False
            if re.search(r"\bPASS", line, re.I):
                return True
    return run_ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--base", required=True)
    ap.add_argument("--brief-file", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--budget-s", type=int, default=2 * SEAT_TIMEOUT_S + 300,
                    help="give up and kill the ringer group after this long (the caller's own timeout is longer)")
    a = ap.parse_args()

    ringer = find_ringer()
    if not ringer:
        print("ringer not found")
        return 3
    cmd, root = ringer

    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    workdir = out / "work"
    # Every run starts clean: a report left by an earlier run must never be read back as this run's.
    shutil.rmtree(workdir, ignore_errors=True)
    for key in SEATS.values():
        (out / f"{key}.md").unlink(missing_ok=True)
    manifest = build_manifest(load_template(root / TEMPLATE), a.repo.resolve(), a.base, a.brief_file.read_text(),
                              workdir, root / "templates" / "adversarial-review",
                              slug=time.strftime("runway-%Y%m%d-%H%M%S"))
    mpath = out / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2))

    lint = subprocess.run([*cmd, "lint", str(mpath)], capture_output=True, text=True)
    run_ok, output = False, ""
    if lint.returncode != 0:
        print(f"ringer lint failed: {(lint.stdout + lint.stderr).strip()[-500:]}", file=sys.stderr)
    else:
        try:
            # Its own process group, so a stop or timeout reaches the codex and claude seat workers too.
            proc = subprocess.Popen([*cmd, "run", str(mpath)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, start_new_session=True)

            def kill_group(sig):
                try:
                    os.killpg(proc.pid, sig)
                except OSError:
                    pass

            def stop(signum, frame):  # pause --stop-now signals this process; take ringer and its workers down with it
                kill_group(signal.SIGTERM)
                sys.exit(1)
            signal.signal(signal.SIGTERM, stop)
            try:
                output, _ = proc.communicate(timeout=a.budget_s)
                run_ok = proc.returncode == 0
            except subprocess.TimeoutExpired:
                kill_group(signal.SIGKILL)
                proc.communicate()
                print("ringer run timed out", file=sys.stderr)
        except OSError as e:
            print(f"ringer run failed: {e}", file=sys.stderr)

    seats = {}
    for seat, key in SEATS.items():
        src = seat_report(workdir, key) if workdir.is_dir() else None
        if src is None:
            seats[seat] = {"status": "MISSING", "report": None}
            continue
        dest = out / f"{key}.md"
        shutil.copyfile(src, dest)
        # A report that exists is kept even when the check failed (it rejects honest prose like "patched the").
        seats[seat] = {"status": "PASS" if seat_passed(output, key, run_ok) else "FAIL", "report": str(dest)}
    print(json.dumps({"seats": seats}))
    return 0 if any(s["report"] for s in seats.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
