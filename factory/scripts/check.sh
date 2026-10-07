#!/usr/bin/env bash
# Runway check_cmd for dc-dev-plugins: every suite must pass.
#   repo tests, every factory/experiments/*/test/test_*.sh (and test_*.py), the
#   plugin's own tests (factory/plugin/*/test/test_*.py), and
#   `swift test` in factory/app once factory/app/Package.swift exists.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== pytest tests"
python3 -m pytest tests -q

shopt -s nullglob
for t in factory/experiments/*/test/test_*.sh; do
  echo "== bash $t"
  bash "$t"
done

py_tests=(factory/experiments/*/test/test_*.py factory/plugin/*/test/test_*.py)
if (( ${#py_tests[@]} )); then
  echo "== pytest ${py_tests[*]}"
  python3 -m pytest -q "${py_tests[@]}"
fi

if [[ -f factory/app/Package.swift ]]; then
  echo "== swift test (factory/app)"
  (cd factory/app && swift test)
fi
echo "== check passed"
