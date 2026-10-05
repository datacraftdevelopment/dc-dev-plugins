#!/usr/bin/env bash
# Point a repo at Linear for /wayfinder, /to-tickets and Runway.
#   bash setup.sh <repo> <TEAM-KEY> "<Linear project name>"
# If <repo> doesn't exist, a tiny Python repo is created there (main branch, a smoke test).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${1:?repo path}"; TEAM="${2:?Linear team key, e.g. SF}"; PROJECT="${3:?Linear project name}"
fill() { sed -e "s#{{TEAM}}#$TEAM#g" -e "s#{{PROJECT}}#$PROJECT#g" "$1"; }

if [ ! -d "$REPO/.git" ]; then
  mkdir -p "$REPO/tests"; cd "$REPO"
  git init -q -b main
  printf '# %s\n\nPractice project for the software factory.\n' "$PROJECT" > README.md
  printf 'import unittest\n\n\nclass Smoke(unittest.TestCase):\n    def test_runs(self):\n        self.assertTrue(True)\n' > tests/test_smoke.py
  touch tests/__init__.py
  printf '_pm/\n__pycache__/\n.runway-worktrees/\n' > .gitignore
  git add -A; git commit -qm "Start practice project"
  echo "Created $REPO"
fi
cd "$REPO"
mkdir -p docs/agents
fill "$HERE/issue-tracker-linear.md" > docs/agents/issue-tracker.md
[ -f runway.json ] || fill "$HERE/runway.json.template" > runway.json
if ! grep -q '^## Agent skills' CLAUDE.md 2>/dev/null; then
  cat >> CLAUDE.md <<MD

## Agent skills

### Issue tracker

Linear, team $TEAM, project "$PROJECT". Runway works the \`ready-for-agent\` queue. See \`docs/agents/issue-tracker.md\`.
MD
fi
git add docs/agents/issue-tracker.md CLAUDE.md runway.json
git commit -qm "Track issues in Linear ($TEAM / $PROJECT); add runway.json" || true
echo "Repo ready: $REPO"
echo "Next: python3 $(cd "$HERE/../../01-runway" && pwd)/runway.py --root \"$REPO\" setup"
