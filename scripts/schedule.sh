#!/usr/bin/env bash
# ============================================================================
# schedule.sh — Installs ONE launchd job that runs the Friday weekly rollup:
#
#   Friday 5:00 PM local time → chained run:
#     1. /meetings-digest --days 7   (pulls the week's Plaud recordings,
#                                     extracts action items, writes to Notion)
#     2. /weekly-rollup              (synthesizes the rollup page so the user
#                                     has it for weekend reflection and walks
#                                     into Monday ready)
#
# Note: prior versions (v1.0/v1.1) installed multiple plists (weekly, then
# lunch+EOD). This script unloads any of those during install to keep the
# system in a single coherent state.
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

LABEL_FRIDAY="com.gallant.plaud-meetings-digest.friday-rollup"
PLIST_FRIDAY="$HOME/Library/LaunchAgents/$LABEL_FRIDAY.plist"

# Legacy labels (cleaned up on install)
LEGACY_LABELS=(
  "com.gallant.plaud-meetings-digest"             # v1.0 (weekly, single plist)
  "com.gallant.plaud-meetings-digest.lunch"       # v1.1
  "com.gallant.plaud-meetings-digest.eod"         # v1.1
  "com.gallant.plaud-meetings-digest.weekly-rollup"  # v1.2 dev (Friday 5:30 variant)
)

RUNNER="$HOME/.claude/skills/meetings-digest/scripts/digest-runner.py"
LOG_OUT="$HOME/Library/Logs/plaud-meetings-digest.stdout.log"
LOG_ERR="$HOME/Library/Logs/plaud-meetings-digest.stderr.log"

PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  err "python3 not found on PATH. Cannot schedule."
  exit 1
fi

if [[ ! -f "$RUNNER" ]]; then
  err "Runner not found at $RUNNER. Run install.sh first."
  exit 1
fi

# Clean up legacy plists from prior versions
for label in "${LEGACY_LABELS[@]}"; do
  plist="$HOME/Library/LaunchAgents/$label.plist"
  if [[ -f "$plist" ]]; then
    launchctl unload "$plist" 2>/dev/null || true
    rm -f "$plist"
    warn "Removed legacy schedule: $label"
  fi
done

# Unload the current label too, if previously installed (rerunning install)
if [[ -f "$PLIST_FRIDAY" ]]; then
  launchctl unload "$PLIST_FRIDAY" 2>/dev/null || true
fi

# Detect PATH the runner should inherit. Mac's launchd has a sparse default
# PATH so we explicitly include common Homebrew + user paths.
RUNNER_PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"

mkdir -p "$(dirname "$PLIST_FRIDAY")"
mkdir -p "$HOME/Library/Logs"

# launchd Weekday convention: Sunday=0, Monday=1, ... Friday=5, Saturday=6
cat > "$PLIST_FRIDAY" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL_FRIDAY</string>

  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$RUNNER</string>
    <string>--skills</string>
    <string>meetings-digest</string>
    <string>weekly-rollup</string>
    <string>--source</string>
    <string>friday-rollup</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>5</integer>
    <key>Hour</key><integer>17</integer>
    <key>Minute</key><integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>$LOG_OUT</string>

  <key>StandardErrorPath</key>
  <string>$LOG_ERR</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$RUNNER_PATH</string>
    <key>HOME</key>
    <string>$HOME</string>
  </dict>

  <key>RunAtLoad</key>
  <false/>

  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
EOF

launchctl load "$PLIST_FRIDAY"

ok "Friday rollup schedule installed"
printf "  Fires:    Every Friday at 5:00 PM local time\n"
printf "  Chained: /meetings-digest --days 7  →  /weekly-rollup\n"
printf "  Label:   %s\n" "$LABEL_FRIDAY"
printf "  Logs:    %s\n" "$LOG_OUT"
printf "           %s\n" "$LOG_ERR"
printf "\n"
printf "%bNote: launchd uses LOCAL time. If the Mac timezone is not Eastern,%b\n" "$YELLOW" "$NC"
printf "%bset the Mac TZ to America/New_York via System Settings → General → Date & Time,%b\n" "$YELLOW" "$NC"
printf "%bor edit the Hour value in the plist at ~/Library/LaunchAgents/$LABEL_FRIDAY.plist.%b\n" "$YELLOW" "$NC"
printf "\n"
printf "Verify:    %blaunchctl list | grep plaud%b\n" "$BOLD" "$NC"
printf "Test now:  %blaunchctl start %s%b\n" "$BOLD" "$LABEL_FRIDAY" "$NC"
printf "Disable:   %blaunchctl unload %s%b\n" "$BOLD" "$PLIST_FRIDAY" "$NC"
