#!/bin/bash
# SessionStart: if the repo has a Basecamp client face (.basecamp/config.json),
# print one paragraph of context. Otherwise print nothing and exit 0 — a repo
# without the file must see zero Basecamp behaviour.
#
# Root discovery, in order: $CLAUDE_PROJECT_DIR (when the host sets it), the
# event's cwd from the hook JSON on stdin, then $PWD. The first valid directory
# is authoritative; look for its config there, then at its git toplevel — so
# a session started in a subdirectory still finds the repo's config. The walk
# never goes above the git root: a config elsewhere on disk is not this repo's.
set -u
command -v python3 >/dev/null 2>&1 || exit 0
script_dir="$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)" || exit 0

event_cwd=""
if [ ! -t 0 ]; then
  event_cwd="$(python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("cwd") or "")
except Exception: print("")' 2>/dev/null)" || event_cwd=""
fi

root=""
for start in "${CLAUDE_PROJECT_DIR:-}" "$event_cwd" "$PWD"; do
  [ -n "$start" ] && [ -d "$start" ] || continue
  root="$start"
  break
done
[ -n "$root" ] || exit 0
if [ ! -f "$root/.basecamp/config.json" ]; then
  if command -v git >/dev/null 2>&1; then
    top="$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)" || top=""
    if [ -n "$top" ] && [ -f "$top/.basecamp/config.json" ]; then
      root="$top"
    fi
  fi
fi
[ -f "$root/.basecamp/config.json" ] || exit 0
python3 "$script_dir/../scripts/bc_config.py" --root "$root" --context 2>/dev/null || exit 0
