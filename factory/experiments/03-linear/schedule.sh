#!/usr/bin/env bash
# Pointer: schedule.sh moved to pm/runway/schedule.sh (2026-10-09; was factory/plugin/runway/).
# Kept so commands and notes that name this path keep working.
exec bash "$(cd "$(dirname "$0")/../../../pm/runway" && pwd)/schedule.sh" "$@"
