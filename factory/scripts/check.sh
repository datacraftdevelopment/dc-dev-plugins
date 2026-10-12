#!/usr/bin/env bash
# Runway check_cmd for dc-dev-plugins: every suite must pass.
#   repo tests, every factory/experiments/*/test/test_*.sh (and test_*.py), the
#   the engine's own tests (pm/runway/test/test_*.py), and
#   `swift test` in factory/app once factory/app/Package.swift exists.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# Isolate every suite from this Mac's real ~/.runway (machine-wide pause, quiet time, agents).
RUNWAY_HOME="$(mktemp -d)"; export RUNWAY_HOME
trap 'rm -rf "$RUNWAY_HOME"' EXIT

# A Homebrew upgrade can swap python3 for a new version with no packages (2026-10-12: 3.15 took over,
# every ticket parked on "No module named pytest"). Say so plainly instead of failing inside a suite.
# PYTHON overrides the interpreter (e.g. PYTHON=/opt/homebrew/bin/python3.14) for the whole check: suites and
# fixtures that call plain `python3` get it too, through a shim put first on PATH.
PY="${PYTHON:-python3}"
if [[ -n "${PYTHON:-}" ]]; then
  PY="$(command -v "$PYTHON" || echo "$PYTHON")"
  SHIM="$(mktemp -d)"
  ln -s "$PY" "$SHIM/python3"
  export PATH="$SHIM:$PATH"
  trap 'rm -rf "$RUNWAY_HOME" "$SHIM"' EXIT
fi
if ! "$PY" -c 'import pytest' 2>/dev/null; then
  echo "check.sh: ${PY} ($(command -v "$PY" || echo not found); $("$PY" --version 2>&1 || true)) has no pytest." >&2
  echo "  Fix: $PY -m pip install pytest   (or set PYTHON to an interpreter that has it)" >&2
  exit 2
fi

echo "== pytest tests"
"$PY" -m pytest tests -q

shopt -s nullglob
for t in factory/experiments/*/test/test_*.sh; do
  echo "== bash $t"
  bash "$t"
done

py_tests=(factory/experiments/*/test/test_*.py pm/runway/test/test_*.py)
if (( ${#py_tests[@]} )); then
  echo "== pytest ${py_tests[*]}"
  "$PY" -m pytest -q "${py_tests[@]}"
fi

if [[ -f factory/app/Package.swift ]]; then
  echo "== swift test (factory/app)"
  (cd factory/app && swift test)
fi
echo "== check passed"
