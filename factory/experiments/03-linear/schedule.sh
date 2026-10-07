#!/usr/bin/env bash
# Pointer: schedule.sh moved to factory/plugin/runway/schedule.sh (2026-10-07).
# Kept so commands and notes that name this path keep working.
exec bash "$(cd "$(dirname "$0")/../../plugin/runway" && pwd)/schedule.sh" "$@"
