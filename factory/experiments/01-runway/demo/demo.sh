#!/usr/bin/env bash
# Builds a throwaway repo with five tickets (one human-gated) and runs the loop offline.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RUNWAY="$HERE/../../../plugin/runway/runway.py"
REPO="${1:-$(mktemp -d)/demo-repo}"
mkdir -p "$REPO/.scratch/demo/issues"
cd "$REPO"
git init -q -b main
git config user.email runway@example.com; git config user.name runway
echo "# demo" > README.md
printf '.scratch/\n_pm/\nrunway.json\n' > .gitignore
git add -A && git commit -qm init
cp "$HERE"/tickets/*.md .scratch/demo/issues/
sed "s#DEMO#$HERE#g" "$HERE/runway.json" > runway.json

echo "== loop until only Joe's decisions remain"
python3 "$RUNWAY" loop
echo; echo "== Joe says go on 03"
python3 "$RUNWAY" go 03 "use greet()"
echo; echo "== loop again"
python3 "$RUNWAY" loop
echo; echo "== integration branch log"
git log --oneline runway/integration
echo; echo "Demo repo: $REPO"
