#!/usr/bin/env python3
"""Opt a repo into the Basecamp client face for the pm plugin's session close.

The repo must already have a valid `.basecamp/config.json` (the basecamp CLI's
file — this helper never creates or edits it, and never calls Basecamp). If the
config is present, install the bundled `docs/agents/client-face.md` contract —
ONLY when that file is absent. An existing file is hand-owned and left alone;
a symlink destination is refused outright.

Usage:
  bc_setup.py [--root DIR]

Exit codes: 0 installed or already present · 1 no/invalid config · 2 unsafe path or write failure.
"""
import argparse, json, os, sys

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                        "templates", "client-face.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.getcwd())
    a = ap.parse_args()
    cfg_path = os.path.join(a.root, ".basecamp", "config.json")
    if not os.path.isfile(cfg_path):
        print(f"bc_setup: no {os.path.join(a.root, '.basecamp/config.json')} — this repo has not "
              f"opted into Basecamp. Set the CLI up first (`basecamp setup`, ids per the "
              f"bc-client-face config contract); this helper never generates the config.",
              file=sys.stderr)
        return 1
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise ValueError("top level is not an object")
    except (OSError, ValueError, UnicodeDecodeError) as e:
        print(f"bc_setup: {cfg_path} is not valid JSON ({e}). Fix it and rerun.", file=sys.stderr)
        return 1
    dest = os.path.join(a.root, "docs", "agents", "client-face.md")
    for path in (os.path.join(a.root, "docs"), os.path.dirname(dest), dest):
        if os.path.islink(path):
            print(f"bc_setup: {path} is a symlink — refusing to write through it.", file=sys.stderr)
            return 2
    if os.path.exists(dest):
        if not os.path.isfile(dest):
            print(f"bc_setup: {dest} is not a regular file.", file=sys.stderr)
            return 2
        print(f"bc_setup: {dest} already exists — left untouched (hand edits win).")
        return 0
    try:
        with open(os.path.normpath(TEMPLATE)) as template:
            content = template.read()
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        # Exclusive creation preserves an entry created after the earlier check.
        with open(dest, "x") as output:
            output.write(content)
    except FileExistsError:
        print(f"bc_setup: {dest} appeared during setup — left untouched; inspect it and rerun.", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"bc_setup: cannot install {dest}: {e}", file=sys.stderr)
        return 2
    print(f"bc_setup: installed {dest}. stepping-away will read it at session close; "
          f"edit it freely — setup never overwrites it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
