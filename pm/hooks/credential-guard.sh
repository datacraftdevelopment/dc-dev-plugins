#!/bin/bash
# credential-guard — PreToolUse hook (Bash matcher).
# Blocks `git add` / `git commit` when a credential-shaped file would be
# staged or committed. Deterministic backing for the "never commit
# credentials" rule: a live client credential is already public from
# exactly this mistake once.
#
# Exit 2 = block (message goes to Claude). Exit 0 = allow. Any internal
# failure falls through to allow — this guard must never break git for
# unrelated reasons.

set -u
input=$(cat 2>/dev/null) || exit 0
cmd=$(printf '%s' "$input" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null) || exit 0
[ -z "$cmd" ] && exit 0

# Only care about git add / git commit (any position in a pipeline/&&-chain).
printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?(add|commit|stage)([[:space:]]|$)' || exit 0

# Where git runs: honour `git -C <dir>`, else the hook's cwd.
repo=$(printf '%s' "$cmd" | sed -nE 's/.*git[[:space:]]+-C[[:space:]]+([^[:space:]]+).*/\1/p' | head -1)
[ -n "$repo" ] && cd "$repo" 2>/dev/null
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Credential-shaped paths. Case-insensitive basename / path-segment match.
# Allow-list: examples and templates.
is_secret() {
  local p="$1" b
  b=$(basename "$p")
  case "$(printf '%s' "$b" | tr '[:upper:]' '[:lower:]')" in
    .env.example|.env.sample|.env.template|*.example|*.sample|*.template) return 1 ;;
    account.md|accounts.md|credentials.md|credentials.json|credentials.yaml|credentials.yml|secrets.json|secrets.yaml|secrets.yml) return 0 ;;
    .env|.env.*|*.pem|*.key|*.p12|*.pfx|id_rsa|id_ed25519|*.keystore|.npmrc|.pypirc|.netrc) return 0 ;;
  esac
  case "$p" in
    */secrets/*|secrets/*|*/.ssh/*|.ssh/*|*/.aws/credentials) return 0 ;;
  esac
  return 1
}

candidates=""
if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?commit'; then
  # What's staged now; with -a/--all, modified tracked files too.
  candidates=$(git diff --cached --name-only 2>/dev/null)
  if printf '%s' "$cmd" | grep -Eq 'commit[[:space:]].*(-a([[:space:]]|$)|--all|-am[[:space:]])'; then
    candidates="$candidates
$(git diff --name-only 2>/dev/null)"
  fi
else
  # git add: if it adds everything, check untracked + modified; else the named args.
  addargs=$(printf '%s' "$cmd" | sed -nE 's/.*git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?add[[:space:]]+(.*)$/\2/p' | sed -E 's/[[:space:]]*(&&|\|\||;|\|).*$//')
  if printf ' %s ' "$addargs" | grep -Eq ' (-A|--all|\.|-u|--update|\*) '; then
    candidates=$(git status --porcelain --untracked-files=all 2>/dev/null | sed -E 's/^.{3}//; s/.* -> //')
  else
    candidates=$(printf '%s' "$cmd" | sed -nE 's/.*git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?add[[:space:]]+(.*)$/\2/p' | tr ' ' '\n' | grep -v '^-' )
  fi
fi

hits=""
while IFS= read -r f; do
  [ -z "$f" ] && continue
  f=${f%\"}; f=${f#\"}
  if is_secret "$f"; then hits="$hits
  $f"; fi
done <<< "$candidates"

if [ -n "$hits" ]; then
  {
    echo "credential-guard: BLOCKED — this would stage/commit credential-shaped files:$hits"
    echo "These must stay out of git. Add them to .gitignore (and 'git rm --cached' if already tracked),"
    echo "or stage only the files you mean. Examples/templates (*.example, *.sample) are allowed."
  } >&2
  exit 2
fi
exit 0
