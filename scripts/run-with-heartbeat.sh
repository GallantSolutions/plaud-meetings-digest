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
# ============================================================================

set -uo pipefail

CHECK_ID=""
PING_BASE_URL="https://hc-ping.com"
LOG_PATH=""
BUNDLE_PREFIX="${BUNDLE_PREFIX:-$HOME/Library/Application Support/plaud-meetings-digest}"
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
    --bundle-prefix)
      BUNDLE_PREFIX="$2"; shift 2 ;;
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

rollback_log() {
  local msg="$1"
  local rb_log="$BUNDLE_PREFIX/logs/auto-rollback.log"
  mkdir -p "$(dirname "$rb_log")" 2>/dev/null || return 0
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $msg" >> "$rb_log" 2>/dev/null || true
}

# ---- Auto-rollback function (v2.2.3+) -----------------------------------
# Called when the wrapped command exited non-zero. Checks the update marker;
# if the most-recent auto-update was within 24h AND we haven't already
# rolled back, restores the previous version's bundle snapshot.
# Returns 0 if rollback was performed; 1 otherwise.
attempt_auto_rollback() {
  local marker="$BUNDLE_PREFIX/.last-update.json"
  [[ -f "$marker" ]] || return 1

  # NOTE: must split `local` declaration from assignment — otherwise
  # `local var=$(...); rc=$?` captures `local`'s exit code (always 0),
  # not the subshell's. Splitting them lets `$?` carry the python3 rc.
  local from_version
  from_version=$(python3 -c "
import json, sys
try:
    d = json.load(open('$marker'))
    if d.get('rolled_back'): sys.exit(2)
    from datetime import datetime, timezone
    updated = datetime.fromisoformat(d['updated_at'].replace('Z','+00:00'))
    age_h = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
    if age_h > 24: sys.exit(3)
    print(d.get('from_version',''))
except SystemExit:
    raise
except Exception as e:
    sys.stderr.write(f'marker parse error: {e}\n')
    sys.exit(4)
" 2>/dev/null)
  local py_rc=$?
  if [[ $py_rc -ne 0 ]]; then
    case $py_rc in
      2) rollback_log "rollback already executed for this update — skipping" ;;
      3) rollback_log "update was >24h ago — outside rollback window, skipping" ;;
      *) rollback_log "marker parse failed (code $py_rc)" ;;
    esac
    return 1
  fi

  if [[ -z "$from_version" ]]; then
    rollback_log "marker has no from_version — cannot rollback"
    return 1
  fi

  local snapshot="$BUNDLE_PREFIX/.versions/$from_version"
  if [[ ! -d "$snapshot" ]]; then
    rollback_log "snapshot missing at $snapshot — cannot rollback"
    return 1
  fi

  rollback_log "ROLLING BACK to $from_version (snapshot at $snapshot)"

  # Restore snapshot contents over the bundle prefix. Skip .versions/, logs/,
  # and the marker itself (we update the marker after to set rolled_back=true).
  (
    cd "$snapshot" || exit 1
    find . -mindepth 1 -maxdepth 1 | while read -r item; do
      name=$(basename "$item")
      [[ "$name" == ".versions" || "$name" == "logs" || "$name" == ".last-update.json" ]] && continue
      dest="$BUNDLE_PREFIX/$name"
      [[ -e "$dest" ]] && rm -rf "$dest"
      cp -R "$item" "$dest"
    done
  ) || { rollback_log "ROLLBACK FAILED during file restore"; return 1; }

  # Reset version.txt
  echo "$from_version" > "$BUNDLE_PREFIX/version.txt"

  # Mark the marker as rolled back (one-shot guard)
  python3 - "$marker" <<'PYEOF'
import json, sys
from datetime import datetime, timezone
marker_path = sys.argv[1]
d = json.load(open(marker_path))
d['rolled_back'] = True
d['rolled_back_at'] = datetime.now(timezone.utc).isoformat()
open(marker_path, 'w').write(json.dumps(d, indent=2))
PYEOF

  # Re-register launchd jobs from the rolled-back schedule.sh
  local schedule_sh="$BUNDLE_PREFIX/scripts/schedule.sh"
  if [[ -x "$schedule_sh" ]]; then
    "$schedule_sh" --config "$HOME/.claude/skills/meetings-digest/config.json" >/dev/null 2>&1 || rollback_log "schedule.sh re-registration after rollback failed"
  fi

  rollback_log "ROLLBACK COMPLETE — bundle restored to $from_version"
  return 0
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

# ---- Auto-rollback (v2.2.3+) --------------------------------------------
# If the wrapped command failed AND we recently auto-updated, restore the
# previous version. Self-healing safety net: the client doesn't have to
# notice; the next scheduled run executes on the rolled-back code.
if [[ $EXIT_CODE -ne 0 ]]; then
  if attempt_auto_rollback; then
    # The rollback function logs success; ping with 'fail' suffix so the
    # operator gets the alert AND the dashboard shows the failure event.
    send_ping "fail"
    exit $EXIT_CODE
  fi
fi

# ---- Outcome ping --------------------------------------------------------
# Healthchecks accepts /<id>/<exit-code> directly: 0 is success, non-zero is
# treated as failure and triggers the configured notification channel.
send_ping "$EXIT_CODE"

exit $EXIT_CODE
