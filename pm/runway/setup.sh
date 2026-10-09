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
  TRACKER_LINE="GitHub Issues, repo $GH_REPO."
  MSG="Track issues in GitHub ($GH_REPO); add runway.json"
else
  fill "$HERE/issue-tracker-linear.md" > docs/agents/issue-tracker.md
  [ -f runway.json ] || fill "$HERE/runway.json.template" > runway.json
  TRACKER_LINE="Linear, team $TEAM, project \"$PROJECT\"."
  MSG="Track issues in Linear ($TEAM / $PROJECT); add runway.json"
fi
# Matt's other two docs: seed when missing, never overwrite (his setup or Joe's edits win).
STAGE=(docs/agents/issue-tracker.md CLAUDE.md runway.json)
if [ ! -f docs/agents/triage-labels.md ]; then
  cp "$HERE/triage-labels.md.template" docs/agents/triage-labels.md; STAGE+=(docs/agents/triage-labels.md)
fi
if [ ! -f docs/agents/domain.md ]; then
  cp "$HERE/domain.md.template" docs/agents/domain.md; STAGE+=(docs/agents/domain.md)
fi
# The Agent skills block has Matt's three sub-blocks; an existing block is left alone.
if ! grep -q '^## Agent skills' CLAUDE.md 2>/dev/null; then
  cat >> CLAUDE.md <<MD

## Agent skills

### Issue tracker

$TRACKER_LINE Runway works the \`ready-for-agent\` queue. See \`docs/agents/issue-tracker.md\`.

### Triage labels

Matt's five defaults, plus Runway's \`go\`, \`needs-human\` and \`spec\`. See \`docs/agents/triage-labels.md\`.

### Domain docs

Single-context: \`GLOSSARY.md\` and \`docs/adr/\` at the repo root, created when first needed. See \`docs/agents/domain.md\`.
MD
fi
# Stage only what this run owns; a dirty worker-env.md or a kept doc must not ride along.
git add -- "${STAGE[@]}"
git commit -qm "$MSG" -- "${STAGE[@]}" || true
echo "Repo ready: $REPO"
echo "Next: python3 \"$HERE/runway.py\" --root \"$REPO\" setup"
