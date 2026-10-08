#!/usr/bin/env bash
# Point a repo at Linear or GitHub for /wayfinder, /to-tickets and Runway.
#   bash setup.sh <repo> <TEAM-KEY> "<Linear project name>"
#   bash setup.sh <repo> --github [owner/name]     (owner/name defaults to the clone's github.com origin)
# If <repo> doesn't exist, a tiny Python repo is created there (main branch, a smoke test).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${1:?repo path}"
TEAM=""; GH_REPO=""
if [ "${2:-}" = "--github" ]; then
  TRACKER=github; GH_REPO="${3:-}"
  if [ -z "$GH_REPO" ] && [ -d "$REPO/.git" ]; then
    GH_REPO="$(git -C "$REPO" remote get-url origin 2>/dev/null | sed -nE 's#.*github\.com[:/]([^/ ]+/[^/ ]+)$#\1#p' | sed -E 's#/$##; s#\.git$##')" || true
  fi
  [ -n "$GH_REPO" ] || { echo "No GitHub repo: pass owner/name (this clone has no github.com origin)." >&2; exit 1; }
  case "$GH_REPO" in */*) ;; *) echo "GitHub repo must look like owner/name, got $GH_REPO" >&2; exit 1;; esac
  PROJECT="$(basename "$REPO")"
else
  TRACKER=linear
  TEAM="${2:?Linear team key, e.g. SF}"; PROJECT="${3:?Linear project name}"
fi
mkdir -p "$REPO"; REPO="$(cd "$REPO" && pwd)"
fill() { sed -e "s#{{TEAM}}#$TEAM#g" -e "s#{{PROJECT}}#$PROJECT#g" -e "s#{{REPO}}#$GH_REPO#g" "$1"; }

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
if [ "$TRACKER" = github ]; then
  fill "$HERE/issue-tracker-github.md" > docs/agents/issue-tracker.md
  [ -f runway.json ] || fill "$HERE/runway.json.github.template" > runway.json
  if ! grep -q '^## Agent skills' CLAUDE.md 2>/dev/null; then
    cat >> CLAUDE.md <<MD

## Agent skills

### Issue tracker

GitHub Issues, repo $GH_REPO. Runway works the \`ready-for-agent\` queue. See \`docs/agents/issue-tracker.md\`.
MD
  fi
  git add docs/agents/issue-tracker.md CLAUDE.md runway.json
  git commit -qm "Track issues in GitHub ($GH_REPO); add runway.json" || true
else
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
fi
echo "Repo ready: $REPO"
echo "Next: python3 \"$HERE/runway.py\" --root \"$REPO\" setup"
