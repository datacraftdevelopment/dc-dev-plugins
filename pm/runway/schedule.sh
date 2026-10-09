#!/usr/bin/env bash
# Run Runway on a schedule with launchd (macOS), so nothing waits for Joe to start it.
#   bash schedule.sh install <repo> [minutes=10]   # load a LaunchAgent that runs `runway loop`
#   bash schedule.sh run <repo>                     # fire it once now
#   bash schedule.sh status <repo>                  # is it loaded; last log lines
#   bash schedule.sh uninstall <repo>
# Each run takes a lock, so a long run is never doubled up. Output: <repo>/_pm/launchd.log
set -euo pipefail
CMD="${1:?install|run|status|uninstall}"; REPO="$(cd "${2:?repo path}" && pwd)"; MIN="${3:-10}"
RUNWAY="$(cd "$(dirname "$0")" && pwd)/runway.py"
NAME="$(basename "$REPO" | tr -c 'A-Za-z0-9\n' '-')"
LABEL="com.joe.runway.$NAME"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

case "$CMD" in
install)
  mkdir -p "$REPO/_pm" "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/bin/zsh</string><string>-lc</string>
    <string>cd "$REPO" &amp;&amp; python3 "$RUNWAY" --root "$REPO" loop --max-ticks 20</string>
  </array>
  <key>StartInterval</key><integer>$((MIN * 60))</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$REPO/_pm/launchd.log</string>
  <key>StandardErrorPath</key><string>$REPO/_pm/launchd.log</string>
</dict></plist>
PL
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$PLIST"
  echo "Loaded $LABEL: runway loop every $MIN min on $REPO"
  ;;
run) launchctl kickstart "$DOMAIN/$LABEL"; echo "Fired $LABEL; tail -f $REPO/_pm/launchd.log" ;;
status)
  launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E 'state|last exit|run interval' || echo "$LABEL is not loaded"
  tail -n 15 "$REPO/_pm/launchd.log" 2>/dev/null || true
  ;;
uninstall) launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true; rm -f "$PLIST"; echo "Removed $LABEL" ;;
*) echo "unknown command $CMD"; exit 2 ;;
esac
