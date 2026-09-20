#!/usr/bin/env python3
"""Run from the ROOT of a git worktree of the Marvel repo: python3 verify.py <acceptance test files...>
Links the main checkout's node_modules, copies the orchestrator's acceptance tests in, runs the
whole suite plus typecheck and lint, then removes what it added. Exit 0 only if everything passed."""
import os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN_MODULES = Path("/Users/joe/Agentic-Mini/RPG/Marvel/apps/marvel/node_modules")
app = Path.cwd() / "apps" / "marvel"
if not app.is_dir():
    sys.exit(f"verify: run me from the worktree root; {app} does not exist")
link, accept = app / "node_modules", app / "src" / "__accept"
made_link = False
status = 1
try:
    if not link.exists():
        os.symlink(MAIN_MODULES, link)
        made_link = True
    if accept.exists():
        shutil.rmtree(accept)
    accept.mkdir(parents=True)
    for name in sys.argv[1:]:
        shutil.copy(HERE / "accept" / name, accept / name)
    steps = [
        ["npx", "next", "typegen"],
        ["npx", "vitest", "run"],
        ["npx", "tsc", "--noEmit"],
        ["npx", "eslint", "src"],
    ]
    for cmd in steps:
        print(f"verify: $ {' '.join(cmd)}", flush=True)
        done = subprocess.run(cmd, cwd=app, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        tail = "\n".join(done.stdout.splitlines()[-60:])
        if done.returncode != 0:
            print(tail)
            print(f"verify: FAILED at: {' '.join(cmd)}")
            status = done.returncode
            break
    else:
        print("verify: all steps passed")
        status = 0
finally:
    shutil.rmtree(accept, ignore_errors=True)
    if made_link and link.is_symlink():
        link.unlink()
sys.exit(status)
