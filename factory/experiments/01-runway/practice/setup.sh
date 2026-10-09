#!/usr/bin/env bash
# Creates the practice repo for Runway's first real run.
# Usage: bash setup.sh [destination]   (default: ~/Agentic-Mini/_Sandbox/runway/runway-practice)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$HOME/Agentic-Mini/_Sandbox/runway/runway-practice}"
if [ -e "$DEST" ]; then echo "$DEST already exists; pick another path or remove it." >&2; exit 1; fi
mkdir -p "$DEST"
cp -R "$HERE/seed/." "$DEST/"
mkdir -p "$DEST/.scratch/hours/issues"
cp "$HERE"/tickets/*.md "$DEST/.scratch/hours/issues/"
cp "$HERE/runway.json" "$DEST/runway.json"
cd "$DEST"
git init -q -b main
git add -A
git commit -qm "Seed hours practice repo"
python3 -m unittest discover -s tests -q
echo
echo "Practice repo ready at $DEST"
echo "Run:  python3 \"$HERE/../../../../pm/runway/runway.py\" --root \"$DEST\" loop"
