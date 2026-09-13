#!/usr/bin/env python3
"""Read and validate a repo's .basecamp/config.json for the basecamp-dc plugin.

The file is the opt-in switch: no file → this plugin has nothing to say.
The basecamp CLI reads project_id / todoset_id / todolist_id from the same file;
basecamp-dc adds two optional blocks it alone reads:

  "lists": { "shipped": "<id>", "active": "<id>", "backlog": "<id>",
             "requests": "<id>", "questions": "<id>" }
  "docs":  { "what_shipped": "<id>", "how_it_works": "<id>" }

Usage:
  bc_config.py [--root DIR]            # print the parsed config as JSON (exit 1 if absent)
  bc_config.py [--root DIR] --context  # one paragraph for the session-start hook; silent if absent
  bc_config.py [--root DIR] --require shipped,active,what_shipped
                                       # exit 2 with a message naming what's missing
"""
import argparse, json, os, sys

LIST_KEYS = ("shipped", "active", "backlog", "requests", "questions")
DOC_KEYS = ("what_shipped", "how_it_works")


def load(root):
    path = os.path.join(root, ".basecamp", "config.json")
    if not os.path.isfile(path):
        return None, path
    with open(path) as f:
        return json.load(f), path


def missing(cfg, wanted):
    lists = cfg.get("lists") or {}
    docs = cfg.get("docs") or {}
    out = []
    for w in wanted:
        if w in LIST_KEYS and not lists.get(w):
            out.append(f"lists.{w}")
        elif w in DOC_KEYS and not docs.get(w):
            out.append(f"docs.{w}")
        elif w not in LIST_KEYS + DOC_KEYS and not cfg.get(w):
            out.append(w)
    return out


def context(cfg):
    lists = cfg.get("lists") or {}
    docs = cfg.get("docs") or {}
    parts = [f"This repo has a Basecamp client face (project {cfg.get('project_id', '?')})."]
    if lists:
        parts.append("Lists: " + ", ".join(f"{k} {v}" for k, v in lists.items() if v) + ".")
    else:
        parts.append("No `lists` block yet — bc-close-out and friends will ask for one.")
    if docs:
        parts.append("Docs: " + ", ".join(f"{k} {v}" for k, v in docs.items() if v) + ".")
    parts.append("Everything written there is client-visible. Load the bc-client-face skill before "
                 "creating, moving, or editing anything in Basecamp; confirm writes with `basecamp api get`.")
    return " ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ap.add_argument("--context", action="store_true")
    ap.add_argument("--require", default="")
    a = ap.parse_args()
    cfg, path = load(a.root)
    if cfg is None:
        if a.context:
            return 0
        print(f"bc_config: no {path} — this repo has no Basecamp client face.", file=sys.stderr)
        return 1
    if a.context:
        print(context(cfg))
        return 0
    if a.require:
        miss = missing(cfg, [w.strip() for w in a.require.split(",") if w.strip()])
        if miss:
            print(f"bc_config: {path} is missing {', '.join(miss)}. Add the ids (find them with "
                  f"`basecamp todolists list --todoset <set> --json`, `basecamp files list --json`) "
                  f"and rerun.", file=sys.stderr)
            return 2
    print(json.dumps(cfg, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
