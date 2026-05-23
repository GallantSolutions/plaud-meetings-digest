#!/usr/bin/env bash
# ============================================================================
# auto-update.sh — Gallant standard auto-updater (Mac/Linux)
# ============================================================================
# Checks GitHub Releases for a newer version of the bundle. If found:
#   1. Snapshots the current bundle to <prefix>/.versions/<old-tag>/
#   2. Downloads + extracts the new release tarball
#   3. Replaces the bundle files (preserves config.json + state/)
#   4. Re-runs scripts/schedule.sh to refresh launchd jobs
#   5. Updates version.txt
#
# Pinned versions: if config.gallant_auto_update.pinned_version is set, the
# updater only updates to that exact tag (or does nothing if already there).
#
# Intentionally silent — no prompts, no read commands. Designed to run from
# a launchd job at 3:00 AM local time. All output goes to the log.
#
# Heartbeat: this script does NOT emit heartbeat pings itself — it's
# expected to be wrapped by run-with-heartbeat.sh via the launchd plist.
# ============================================================================

set -euo pipefail

BUNDLE_PREFIX="${BUNDLE_PREFIX:-$HOME/Library/Application Support/plaud-meetings-digest}"
CONFIG_PATH="${CONFIG_PATH:-$HOME/.claude/skills/meetings-digest/config.json}"
REPO=""
DRY_RUN=0

# ---- Parse args (override defaults) --------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle-prefix) BUNDLE_PREFIX="$2"; shift 2 ;;
    --config-path)   CONFIG_PATH="$2"; shift 2 ;;
    --repo)          REPO="$2"; shift 2 ;;
    --dry-run)       DRY_RUN=1; shift ;;
    *) echo "auto-update.sh: unknown arg: $1" >&2; exit 2 ;;
  esac
done

LOG_DIR="$HOME/Library/Logs"
LOG_PATH="$LOG_DIR/plaud-meetings-digest.auto-update.log"
mkdir -p "$LOG_DIR"

log() {
  local line="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1"
  echo "$line" >> "$LOG_PATH"
  echo "$line"
}

log "=== auto-update.sh starting ==="
log "Bundle prefix: $BUNDLE_PREFIX"
log "Config path:   $CONFIG_PATH"

if [[ ! -f "$CONFIG_PATH" ]]; then
  log "ERROR: config not found at $CONFIG_PATH"
  exit 1
fi

# ---- Read config via python (portable JSON parsing) ----------------------
read_config() {
  python3 - "$CONFIG_PATH" <<'PYEOF'
import json, sys
cfg = json.load(open(sys.argv[1]))
au = cfg.get("gallant_auto_update", {})
print("enabled=" + ("true" if au.get("enabled") else "false"))
print("repo=" + (au.get("repo") or ""))
print("channel=" + (au.get("channel") or "latest"))
print("pinned=" + (au.get("pinned_version") or ""))
PYEOF
}

eval "$(read_config | sed 's/^/CONF_/')"

if [[ "${CONF_enabled:-false}" != "true" ]]; then
  log "Auto-update disabled in config — exiting cleanly"
  exit 0
fi

if [[ -z "$REPO" ]]; then REPO="${CONF_repo:-}"; fi
if [[ -z "$REPO" ]]; then
  log "ERROR: no repo configured (config.gallant_auto_update.repo missing)"
  exit 1
fi

CHANNEL="${CONF_channel:-latest}"
PINNED="${CONF_pinned:-}"

# ---- Read current version ------------------------------------------------
VERSION_FILE="$BUNDLE_PREFIX/version.txt"
CURRENT_VERSION=""
if [[ -f "$VERSION_FILE" ]]; then
  CURRENT_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
fi
log "Current version: '$CURRENT_VERSION'"

# ---- Resolve target version ----------------------------------------------
TARGET_VERSION=""
if [[ -n "$PINNED" ]]; then
  TARGET_VERSION="$PINNED"
  log "Pinned to: $TARGET_VERSION"
else
  log "Channel: $CHANNEL — resolving via GitHub Releases API"
  if [[ "$CHANNEL" == "latest" ]]; then
    REL_URL="https://api.github.com/repos/$REPO/releases/latest"
  else
    REL_URL="https://api.github.com/repos/$REPO/releases/tags/$CHANNEL"
  fi
  TARGET_VERSION=$(curl -fsS -m 30 "$REL_URL" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tag_name',''))" 2>/dev/null || echo "")
  if [[ -z "$TARGET_VERSION" ]]; then
    log "ERROR: could not resolve target version from $REL_URL"
    exit 1
  fi
fi
log "Target version: $TARGET_VERSION"

if [[ "$TARGET_VERSION" == "$CURRENT_VERSION" ]]; then
  log "Already on $TARGET_VERSION — nothing to do"
  exit 0
fi

if [[ $DRY_RUN -eq 1 ]]; then
  log "DRY RUN: would update $CURRENT_VERSION -> $TARGET_VERSION"
  exit 0
fi

# ---- Snapshot current bundle ---------------------------------------------
if [[ -n "$CURRENT_VERSION" ]]; then
  SNAPSHOT_DIR="$BUNDLE_PREFIX/.versions/$CURRENT_VERSION"
  if [[ -d "$SNAPSHOT_DIR" ]]; then
    log "Snapshot already exists at $SNAPSHOT_DIR — leaving in place"
  else
    log "Snapshotting current bundle to $SNAPSHOT_DIR"
    mkdir -p "$SNAPSHOT_DIR"
    # rsync everything except .versions (would recurse) and logs
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --exclude '.versions/' --exclude 'logs/' "$BUNDLE_PREFIX/" "$SNAPSHOT_DIR/" || log "WARN: snapshot rsync had issues — proceeding anyway"
    else
      # cp fallback
      (cd "$BUNDLE_PREFIX" && find . -mindepth 1 -maxdepth 1 ! -name '.versions' ! -name 'logs' -exec cp -R {} "$SNAPSHOT_DIR/" \;) || log "WARN: snapshot cp had issues"
    fi
  fi
fi

# ---- Download + extract new release --------------------------------------
TMP_TAR="$(mktemp -t gallant-update.XXXXXX).tar.gz"
TMP_EXTRACT="$(mktemp -d -t gallant-update-extract.XXXXXX)"

TARBALL_URL="https://github.com/$REPO/archive/refs/tags/$TARGET_VERSION.tar.gz"
log "Downloading $TARBALL_URL"
if ! curl -fsSL -m 300 -o "$TMP_TAR" "$TARBALL_URL"; then
  log "ERROR: download failed"
  rm -f "$TMP_TAR"; rm -rf "$TMP_EXTRACT"
  exit 1
fi

log "Extracting to $TMP_EXTRACT"
tar -xzf "$TMP_TAR" -C "$TMP_EXTRACT"
EXTRACTED_DIR=$(find "$TMP_EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -1)
if [[ -z "$EXTRACTED_DIR" ]]; then
  log "ERROR: extracted folder not found"
  rm -f "$TMP_TAR"; rm -rf "$TMP_EXTRACT"
  exit 1
fi

# ---- Replace bundle files (preserve client-customized parts) -------------
# OVERWRITE: install.*, bootstrap.*, uninstall.*, README, docs/, scripts/,
#            skills/<*>/SKILL.md, config/*.template.json
# PRESERVE:  .versions/, logs/, ~/.claude/skills/<name>/config.json,
#            ~/.claude/skills/<name>/state/
log "Replacing bundle files at $BUNDLE_PREFIX"
mkdir -p "$BUNDLE_PREFIX"
(
  cd "$EXTRACTED_DIR"
  find . -mindepth 1 -maxdepth 1 | while read -r item; do
    name=$(basename "$item")
    dest="$BUNDLE_PREFIX/$name"
    if [[ -e "$dest" ]]; then rm -rf "$dest"; fi
    cp -R "$item" "$dest"
  done
)

# ---- Push updated SKILL.md + scripts/*.py into ~/.claude/skills/ ---------
LIVE_SKILLS_ROOT="$HOME/.claude/skills"
if [[ -d "$BUNDLE_PREFIX/skills" ]]; then
  for skill_dir in "$BUNDLE_PREFIX/skills"/*/; do
    skill_name=$(basename "$skill_dir")
    live_skill="$LIVE_SKILLS_ROOT/$skill_name"
    if [[ -d "$live_skill" && -f "$skill_dir/SKILL.md" ]]; then
      cp "$skill_dir/SKILL.md" "$live_skill/SKILL.md"
      log "Updated SKILL.md for $skill_name"
    fi
  done
fi

# Copy scripts/*.py into the meetings-digest live install (where the launchd
# jobs point). Build-specific — adjust per-build if a different skill is the
# runtime target.
LIVE_SCRIPTS="$LIVE_SKILLS_ROOT/meetings-digest/scripts"
if [[ -d "$LIVE_SCRIPTS" && -d "$BUNDLE_PREFIX/scripts" ]]; then
  cp "$BUNDLE_PREFIX/scripts"/*.py "$LIVE_SCRIPTS/" 2>/dev/null || true
  log "Updated Python helpers in $LIVE_SCRIPTS"
fi

# ---- Update version stamp ------------------------------------------------
echo "$TARGET_VERSION" > "$VERSION_FILE"
log "Wrote version.txt = $TARGET_VERSION"

# ---- Write update marker (auto-rollback safety net, v2.2.3+) -------------
# The heartbeat wrapper checks this file when a wrapped command fails non-
# zero. If the update was recent (< 24h) AND rolled_back is false, the
# wrapper auto-restores the previous version from .versions/<from_version>/.
# One-shot — the wrapper sets rolled_back: true so subsequent failures
# don't repeat the rollback.
UPDATE_MARKER="$BUNDLE_PREFIX/.last-update.json"
python3 - "$UPDATE_MARKER" "$CURRENT_VERSION" "$TARGET_VERSION" <<'PYEOF'
import json, sys
from datetime import datetime, timezone
marker_path, from_v, to_v = sys.argv[1], sys.argv[2], sys.argv[3]
data = {
    "from_version": from_v,
    "to_version":   to_v,
    "updated_at":   datetime.now(timezone.utc).isoformat(),
    "rolled_back":  False,
}
open(marker_path, "w").write(json.dumps(data, indent=2))
PYEOF
log "Wrote update marker: $UPDATE_MARKER"

# ---- Re-register launchd jobs (in case task definitions changed) ---------
SCHEDULE_SCRIPT="$BUNDLE_PREFIX/scripts/schedule.sh"
if [[ -x "$SCHEDULE_SCRIPT" ]]; then
  log "Re-running schedule.sh to refresh launchd jobs"
  if ! "$SCHEDULE_SCRIPT" --config "$CONFIG_PATH"; then
    log "WARN: schedule.sh failed — jobs may need manual re-registration"
  fi
fi

# ---- Cleanup tmp ---------------------------------------------------------
rm -f "$TMP_TAR"
rm -rf "$TMP_EXTRACT"

log "=== auto-update complete: $CURRENT_VERSION -> $TARGET_VERSION ==="
exit 0
