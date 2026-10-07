#!/usr/bin/env bash
# Offline test of experiment 04: token and session capture, the finish step (review,
# one fix pass, check, PR body, draft PR through a fake gh) and `runway retro`.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RUNWAY="$HERE/../../01-runway/runway.py"
TMP="$(mktemp -d)"
export CLAUDE_CONFIG_DIR="$TMP/claude-home" GH_LOG="$TMP/gh.log"
mkdir -p "$TMP/bin"; ln -s "$HERE/fake_gh.sh" "$TMP/bin/gh"; export PATH="$TMP/bin:$PATH"
git init -q --bare "$TMP/origin.git"
REPO="$TMP/finish-demo"; mkdir -p "$REPO/.scratch/demo/issues"; cd "$REPO"
git init -q -b main; git config user.email runway@example.com; git config user.name runway
git remote add origin "$TMP/origin.git"
echo "# demo" > README.md; printf '.scratch/\n_pm/\nrunway.json\n' > .gitignore
git add -A; git commit -qm init; git push -q origin main
I=.scratch/demo/issues
printf '# Greeting module\n\nStatus: ready\n' > $I/01-greeting.md
printf '# Export\n\nStatus: ready\nBlocked by: 01\n' > $I/02-export.md
printf '# Public name\n\nStatus: ready\nGate: human\nBlocked by: 01\n' > $I/03-public-name.md
cat > runway.json <<JSON
{"agent_cmd": "python3 $HERE/fake_claude.py", "prep_cmd": "python3 $HERE/fake_claude.py",
 "review_cmd": "python3 $HERE/fake_claude.py",
 "check_cmd": "sh -c '! grep -l broken *.txt'", "pr": "draft", "spec": "docs/spec.md"}
JSON
fail() { echo "FAIL: $*"; exit 1; }

echo "== loop 1: 01 done, 02 done on its second attempt, 03 packet; no finish (03 still open)"
python3 "$RUNWAY" loop
[ -f _pm/runway-pr.md ] && fail "finish ran with a ticket open"
grep -q '"attempt": 2' _pm/runway-runs.jsonl || fail "no second attempt logged"

echo; echo "== Joe: go 03"
python3 "$RUNWAY" go 03 "use greet()"
echo; echo "== loop 2: 03 done, then finish: review finding, fix pass, check, PR body, draft PR"
python3 "$RUNWAY" loop
git show runway/integration:greeting.txt | grep -qx hello || fail "fix pass not on the integration branch"
grep -q "## Merge danger" _pm/runway-pr.md || fail "PR body missing merge danger"
grep -q "check still passes" _pm/runway-pr.md || fail "PR body missing fix note"
grep -q "pr create --draft" "$GH_LOG" || fail "no draft PR"
git --git-dir="$TMP/origin.git" rev-parse -q --verify runway/integration >/dev/null || fail "integration not pushed"

echo; echo "== loop 3: nothing new, so no second finish"
python3 "$RUNWAY" loop
[ "$(grep -c '"kind": "finish"' _pm/runway-runs.jsonl)" = 1 ] || fail "finish ran twice on the same head"

echo; echo "== runway finish (forced): updates the existing PR instead of opening another"
python3 "$RUNWAY" finish
grep -q "pr edit" "$GH_LOG" || fail "existing PR not updated"
[ "$(grep -c 'pr create' "$GH_LOG")" = 1 ] || fail "opened a second PR"

echo; echo "== runway retro"
python3 "$RUNWAY" retro
grep -q "demo/02.*needed attempt 2\|demo/02.*failed the check" _pm/runway-retro-prompt.md || fail "retro didn't flag the retried ticket"
grep -q "claude-home/projects/.*\.jsonl" _pm/runway-retro-prompt.md || fail "retro didn't find transcripts"
grep -q "| total | " _pm/runway-retro.md || fail "no usage total"

echo; echo "== gh calls"; cat "$GH_LOG"
echo; echo "PASS ($REPO)"
