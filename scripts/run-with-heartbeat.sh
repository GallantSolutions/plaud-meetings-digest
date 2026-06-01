#!/usr/bin/env bash
# ============================================================================
# run-with-heartbeat.sh — Gallant standard heartbeat wrapper (Mac/Linux)
# ============================================================================
# Wraps any command, pings Healthchecks.io before/after the wrapped run.
#
# Usage (from a launchd plist or cron):
#   /bin/bash /path/to/run-with-heartbeat.sh \
#       --check-id "uuid-from-healthchecks" \
#       --ping-base-url "https://hc-ping.com" \
#       -- python3 /path/to/digest-runner.py --skill meetings-digest --source lunch
#
# Anything after the -- is treated as the wrapped command + its args.
#
# Ping flow:
#   1. curl <base>/<id>/start          (let HC know the job started)
#   2. Run the command, capture exit code
#   3. curl <base>/<id>/<exit-code>    (0 = success, anything else = fail)
#
# Heartbeat pings are best-effort. A failed ping NEVER aborts the wrapped
# command — if the network is down, the job still runs successfully and the
# operator just sees a missed-ping alert on the next scheduled window.
#
# Auto-rollback was removed in v2.5.0 alongside the auto-update deprecation:
# with no self-update there is nothing to roll back.
# ============================================================================

set -uo pipefail

CHECK_ID=""
PING_BASE_URL="https://hc-ping.com"
LOG_PATH=""
REST_ARGS=()

# ---- Parse args ----------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-id)
      CHECK_ID="$2"; shift 2 ;;
    --ping-base-url)
      PING_BASE_URL="$2"; shift 2 ;;
    --log-path)
      LOG_PATH="$2"; shift 2 ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do REST_ARGS+=("$1"); shift; done ;;
    *)
      # Unknown arg or positional — treat as start of command
      while [[ $# -gt 0 ]]; do REST_ARGS+=("$1"); shift; done ;;
  esac
done

log_line() {
  local msg="$1"
  if [[ -n "$LOG_PATH" ]]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $msg" >> "$LOG_PATH" 2>/dev/null || true
  fi
}

# ---- Ping function -------------------------------------------------------
send_ping() {
  local suffix="${1:-}"
  if [[ -z "$CHECK_ID" || "$CHECK_ID" == "null" ]]; then
    return 0  # No check configured — skip silently
  fi
  local url="$PING_BASE_URL/$CHECK_ID"
  if [[ -n "$suffix" ]]; then url="$url/$suffix"; fi
  # Best-effort: 10s timeout, swallow errors, never abort
  curl -fsS -m 10 -o /dev/null "$url" 2>/dev/null || log_line "heartbeat ping failed ($url)"
}

# ---- Start ping ----------------------------------------------------------
send_ping "start"

# ---- Run the wrapped command --------------------------------------------
EXIT_CODE=0
if [[ ${#REST_ARGS[@]} -eq 0 ]]; then
  log_line "no command supplied — nothing to run"
  send_ping "99"
  exit 99
fi

# Disable -e for the wrapped run so we can capture non-zero exits
set +e
"${REST_ARGS[@]}"
EXIT_CODE=$?
set -e

# ---- Outcome ping --------------------------------------------------------
# Bash exit codes are already 0-255; HC accepts /<id>/<exit-code> directly:
# 0 is success, non-zero triggers the configured notification channel.
send_ping "$EXIT_CODE"

exit $EXIT_CODE
