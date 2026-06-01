#!/usr/bin/env bash
# ============================================================================
# schedule.sh — Mac launchd installer (v2.5.0)
#
# Installs THREE jobs:
#   - Daily 11:00 AM     → /meetings-digest (lunch pull)
#   - Daily  4:00 PM     → /meetings-digest (EOD pull)
#   - Friday 4:30 PM     → /weekly-rollup   (rollup across rollup-enabled buckets)
#
# Auto-update is DEPRECATED as of v2.5.0 (operator decision 2026-06-01): the
# nightly self-update fired unreliably and a broken release had no remediation
# path. Updates are now operator-initiated (update.ps1 on Windows; pull + re-run
# install on Mac). This script defensively removes any pre-existing auto-update
# launchd job on re-run.
#
# Every job is wrapped in run-with-heartbeat.sh — pings Healthchecks.io
# before/after so the operator gets alerted when a run misses its window.
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

# ---- Config path (defaults; --config overrides) --------------------------
CONFIG_PATH="$HOME/.claude/skills/meetings-digest/config.json"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG_PATH="$2"; shift 2 ;;
    *) shift ;;
  esac
done

LABEL_LUNCH="com.gallant.plaud-meetings-digest.lunch"
LABEL_EOD="com.gallant.plaud-meetings-digest.eod"
LABEL_ROLLUP="com.gallant.plaud-meetings-digest.rollup"

PLIST_LUNCH="$HOME/Library/LaunchAgents/$LABEL_LUNCH.plist"
PLIST_EOD="$HOME/Library/LaunchAgents/$LABEL_EOD.plist"
PLIST_ROLLUP="$HOME/Library/LaunchAgents/$LABEL_ROLLUP.plist"

# Legacy + deprecated labels we clean up on (re-)install
LEGACY_LABELS=(
  "com.gallant.plaud-meetings-digest"
  "com.gallant.plaud-meetings-digest.friday-rollup"
  "com.gallant.plaud-meetings-digest.weekly-rollup"
  "com.gallant.plaud-meetings-digest.auto-update"
)

RUNNER="$HOME/.claude/skills/meetings-digest/scripts/digest-runner.py"
LOG_OUT="$HOME/Library/Logs/plaud-meetings-digest.stdout.log"
LOG_ERR="$HOME/Library/Logs/plaud-meetings-digest.stderr.log"

# Bundle prefix — where the heartbeat wrapper lives.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_PREFIX="$(dirname "$SCRIPT_DIR")"
if [[ ! -f "$BUNDLE_PREFIX/scripts/run-with-heartbeat.sh" ]]; then
  if [[ -f "$HOME/Library/Application Support/plaud-meetings-digest/scripts/run-with-heartbeat.sh" ]]; then
    BUNDLE_PREFIX="$HOME/Library/Application Support/plaud-meetings-digest"
  fi
fi
HEARTBEAT_WRAPPER="$BUNDLE_PREFIX/scripts/run-with-heartbeat.sh"

PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then err "python3 not found on PATH"; exit 1; fi
if [[ ! -f "$RUNNER" ]]; then err "Runner not found at $RUNNER. Run install.sh first."; exit 1; fi

# ---- Load heartbeat config (best-effort) ---------------------------------
HEARTBEAT_BASE="https://hc-ping.com"
CHECK_LUNCH=""
CHECK_EOD=""
CHECK_ROLLUP=""

if [[ -f "$CONFIG_PATH" ]]; then
  HB_CONFIG=$(python3 - "$CONFIG_PATH" <<'PYEOF' 2>/dev/null || true
import json, sys
try:
    cfg = json.load(open(sys.argv[1]))
    hb = cfg.get("gallant_heartbeat", {})
    print("BASE=" + (hb.get("ping_base_url") or "https://hc-ping.com"))
    checks = hb.get("checks", {})
    print("LUNCH=" + (checks.get("lunch") or ""))
    print("EOD=" + (checks.get("eod") or ""))
    print("ROLLUP=" + (checks.get("rollup") or ""))
except Exception:
    pass
PYEOF
)
  while IFS='=' read -r key value; do
    case "$key" in
      BASE)   HEARTBEAT_BASE="${value:-https://hc-ping.com}" ;;
      LUNCH)  CHECK_LUNCH="$value" ;;
      EOD)    CHECK_EOD="$value" ;;
      ROLLUP) CHECK_ROLLUP="$value" ;;
    esac
  done <<< "$HB_CONFIG"
fi

# ---- Unload current + remove legacy/deprecated --------------------------
for L in "$LABEL_LUNCH" "$LABEL_EOD" "$LABEL_ROLLUP" "${LEGACY_LABELS[@]}"; do
  P="$HOME/Library/LaunchAgents/$L.plist"
  if [[ -f "$P" ]]; then
    launchctl unload "$P" 2>/dev/null || true
    if [[ " ${LEGACY_LABELS[*]} " == *" $L "* ]]; then
      rm -f "$P"
      warn "Removed legacy/deprecated schedule: $L"
    fi
  fi
done

RUNNER_PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"
mkdir -p "$(dirname "$PLIST_LUNCH")"
mkdir -p "$HOME/Library/Logs"

# ---- Build a launchd plist (wrapped or direct) ---------------------------
write_plist() {
  local label="$1"
  local plist_path="$2"
  local check_id="$3"
  local calendar_xml="$4"
  shift 4
  local inner_args=("$@")

  local program_args=""
  if [[ -n "$check_id" && -f "$HEARTBEAT_WRAPPER" ]]; then
    program_args="    <string>/bin/bash</string>
    <string>$HEARTBEAT_WRAPPER</string>
    <string>--check-id</string><string>$check_id</string>
    <string>--ping-base-url</string><string>$HEARTBEAT_BASE</string>
    <string>--</string>"
    for arg in "${inner_args[@]}"; do
      program_args+="
    <string>$arg</string>"
    done
  else
    for arg in "${inner_args[@]}"; do
      program_args+="
    <string>$arg</string>"
    done
    program_args="${program_args#$'\n'}"
  fi

  cat > "$plist_path" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
$program_args
  </array>
$calendar_xml
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

daily_calendar() {
  local hour="$1"; local minute="$2"
  printf '  <key>StartCalendarInterval</key>\n  <dict>\n    <key>Hour</key><integer>%s</integer>\n    <key>Minute</key><integer>%s</integer>\n  </dict>' "$hour" "$minute"
}

weekly_calendar() {
  local weekday="$1"; local hour="$2"; local minute="$3"
  printf '  <key>StartCalendarInterval</key>\n  <dict>\n    <key>Weekday</key><integer>%s</integer>\n    <key>Hour</key><integer>%s</integer>\n    <key>Minute</key><integer>%s</integer>\n  </dict>' "$weekday" "$hour" "$minute"
}

# ---- Write the three plists ----------------------------------------------
write_plist "$LABEL_LUNCH"  "$PLIST_LUNCH"  "$CHECK_LUNCH" \
  "$(daily_calendar 11 0)" \
  "$PYTHON_BIN" "$RUNNER" "--skill" "meetings-digest" "--source" "lunch"

write_plist "$LABEL_EOD"    "$PLIST_EOD"    "$CHECK_EOD" \
  "$(daily_calendar 16 0)" \
  "$PYTHON_BIN" "$RUNNER" "--skill" "meetings-digest" "--source" "eod"

write_plist "$LABEL_ROLLUP" "$PLIST_ROLLUP" "$CHECK_ROLLUP" \
  "$(weekly_calendar 5 16 30)" \
  "$PYTHON_BIN" "$RUNNER" "--skill" "weekly-rollup" "--source" "rollup"

launchctl load "$PLIST_LUNCH"
launchctl load "$PLIST_EOD"
launchctl load "$PLIST_ROLLUP"

ok "Schedule installed (3 jobs — auto-update deprecated)"
printf "  Lunch:   11:00 AM daily   (label %s)\n" "$LABEL_LUNCH"
printf "  EOD:      4:00 PM daily   (label %s)\n" "$LABEL_EOD"
printf "  Rollup:   4:30 PM Friday  (label %s)\n" "$LABEL_ROLLUP"
printf "  Logs:    %s\n" "$LOG_OUT"
printf "\n"
if [[ -n "$CHECK_LUNCH$CHECK_EOD$CHECK_ROLLUP" ]]; then
  ok "Heartbeat: wrapping enabled (base: $HEARTBEAT_BASE)"
else
  warn "Heartbeat: no check IDs configured — operator will not be alerted to silent failures"
fi
printf "\n"
printf "Updates:   operator-initiated (auto-update deprecated in v2.5.0)\n"
printf "Verify:    %blaunchctl list | grep plaud%b\n" "$BOLD" "$NC"
printf "Test now:  %blaunchctl start %s%b\n" "$BOLD" "$LABEL_LUNCH" "$NC"
