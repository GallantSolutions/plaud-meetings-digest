#!/usr/bin/env bash
# ============================================================================
# schedule.sh — Mac launchd installer (v2.0.0)
#
# Installs THREE jobs:
#   - Daily 12:30 PM     → /meetings-digest (lunch pull)
#   - Daily  5:00 PM     → /meetings-digest (EOD pull)
#   - Friday 5:30 PM     → /weekly-rollup   (Kingsway Pharma rollup)
# ============================================================================

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { printf "%b✓ %s%b\n" "$GREEN" "$1" "$NC"; }
warn() { printf "%b⚠ %s%b\n" "$YELLOW" "$1" "$NC"; }
err()  { printf "%b✗ %s%b\n" "$RED" "$1" "$NC"; }

LABEL_LUNCH="com.gallant.plaud-meetings-digest.lunch"
LABEL_EOD="com.gallant.plaud-meetings-digest.eod"
LABEL_ROLLUP="com.gallant.plaud-meetings-digest.rollup"

PLIST_LUNCH="$HOME/Library/LaunchAgents/$LABEL_LUNCH.plist"
PLIST_EOD="$HOME/Library/LaunchAgents/$LABEL_EOD.plist"
PLIST_ROLLUP="$HOME/Library/LaunchAgents/$LABEL_ROLLUP.plist"

# Legacy labels we clean up on (re-)install
LEGACY_LABELS=(
  "com.gallant.plaud-meetings-digest"
  "com.gallant.plaud-meetings-digest.friday-rollup"
  "com.gallant.plaud-meetings-digest.weekly-rollup"
)

RUNNER="$HOME/.claude/skills/meetings-digest/scripts/digest-runner.py"
LOG_OUT="$HOME/Library/Logs/plaud-meetings-digest.stdout.log"
LOG_ERR="$HOME/Library/Logs/plaud-meetings-digest.stderr.log"

PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then err "python3 not found on PATH"; exit 1; fi
if [[ ! -f "$RUNNER" ]]; then err "Runner not found at $RUNNER. Run install.sh first."; exit 1; fi

# Unload current + legacy
for L in "$LABEL_LUNCH" "$LABEL_EOD" "$LABEL_ROLLUP" "${LEGACY_LABELS[@]}"; do
  P="$HOME/Library/LaunchAgents/$L.plist"
  if [[ -f "$P" ]]; then
    launchctl unload "$P" 2>/dev/null || true
    if [[ " ${LEGACY_LABELS[*]} " == *" $L "* ]]; then
      rm -f "$P"
      warn "Removed legacy schedule: $L"
    fi
  fi
done

RUNNER_PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"
mkdir -p "$(dirname "$PLIST_LUNCH")"
mkdir -p "$HOME/Library/Logs"

# ---- Build a daily plist (no weekday key) ---------------------------------
write_daily_plist() {
  local label="$1"; local plist_path="$2"; local hour="$3"; local minute="$4"; local skill="$5"; local nick="$6"
  cat > "$plist_path" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$RUNNER</string>
    <string>--skill</string><string>$skill</string>
    <string>--source</string><string>$nick</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$hour</integer>
    <key>Minute</key><integer>$minute</integer>
  </dict>
  <key>StandardOutPath</key><string>$LOG_OUT</string>
  <key>StandardErrorPath</key><string>$LOG_ERR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$RUNNER_PATH</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
  <key>RunAtLoad</key><false/>
  <key>KeepAlive</key><false/>
</dict>
</plist>
EOF
}

# ---- Build a weekly plist (specific weekday) ------------------------------
write_weekly_plist() {
  local label="$1"; local plist_path="$2"; local weekday="$3"; local hour="$4"; local minute="$5"; local skill="$6"; local nick="$7"
  cat > "$plist_path" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$RUNNER</string>
    <string>--skill</string><string>$skill</string>
    <string>--source</string><string>$nick</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>$weekday</integer>
    <key>Hour</key><integer>$hour</integer>
    <key>Minute</key><integer>$minute</integer>
  </dict>
  <key>StandardOutPath</key><string>$LOG_OUT</string>
  <key>StandardErrorPath</key><string>$LOG_ERR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$RUNNER_PATH</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
  <key>RunAtLoad</key><false/>
  <key>KeepAlive</key><false/>
</dict>
</plist>
EOF
}

write_daily_plist  "$LABEL_LUNCH"  "$PLIST_LUNCH"      12 30 "meetings-digest" "lunch"
write_daily_plist  "$LABEL_EOD"    "$PLIST_EOD"        17  0 "meetings-digest" "eod"
write_weekly_plist "$LABEL_ROLLUP" "$PLIST_ROLLUP"  5  17 30 "weekly-rollup"   "rollup"

launchctl load "$PLIST_LUNCH"
launchctl load "$PLIST_EOD"
launchctl load "$PLIST_ROLLUP"

ok "Schedule installed (3 jobs)"
printf "  Lunch:   12:30 PM daily  (label %s)\n" "$LABEL_LUNCH"
printf "  EOD:      5:00 PM daily  (label %s)\n" "$LABEL_EOD"
printf "  Rollup:   5:30 PM Friday (label %s)\n" "$LABEL_ROLLUP"
printf "  Logs:    %s\n" "$LOG_OUT"
printf "\n"
printf "Verify:    %blaunchctl list | grep plaud%b\n" "$BOLD" "$NC"
printf "Test now:  %blaunchctl start %s%b\n" "$BOLD" "$LABEL_LUNCH" "$NC"
