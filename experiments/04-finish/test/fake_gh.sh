#!/usr/bin/env bash
# Stand-in for gh: records each call, pretends no PR exists, then that one does.
echo "gh $*" >> "$GH_LOG"
case "$1 $2" in
  "pr view") [ -f "$GH_LOG.created" ] && echo "https://github.com/example/demo/pull/1" ; exit 0 ;;
  "pr create") touch "$GH_LOG.created"; echo "https://github.com/example/demo/pull/1" ;;
  "pr edit") echo "https://github.com/example/demo/pull/1" ;;
esac
