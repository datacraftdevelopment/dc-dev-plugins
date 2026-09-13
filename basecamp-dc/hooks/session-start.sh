#!/bin/bash
# SessionStart: if the repo has a Basecamp client face (.basecamp/config.json),
# print one paragraph of context. Otherwise print nothing and exit 0 — a repo
# without the file must see zero Basecamp behaviour.
set -u
root="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$root/.basecamp/config.json" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
script_dir="$(cd -- "${BASH_SOURCE[0]%/*}/../scripts" && pwd)" || exit 0
python3 "$script_dir/bc_config.py" --root "$root" --context 2>/dev/null || exit 0
