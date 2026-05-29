#!/usr/bin/env bash
# ============================================================================
# Plaud Meetings Digest — Installer
# ============================================================================
# Installs the meetings-digest + weekly-rollup skills into Claude Code, wires
# up the Plaud MCP server, configures the output destination (folder or Notion),
# and optionally schedules the Friday 4:30 PM weekly rollup.
#
# Usage:   ./install.sh
# Fail-soft on missing prereqs (prints install commands, exits).
# Re-runnable: idempotent. Re-running updates the skill + reconfigures.
# ============================================================================

set -euo pipefail

# ---- Colors --------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

say()  { printf "%b%s%b\n" "$BLUE" "→ $1" "$NC"; }
ok()   { printf "%b✓ %s%b\n" "$GREEN" "$1" "$NC"; }
warn() { printf "%b⚠ %s%b\n" "$YELLOW" "$1" "$NC"; }
err()  { printf "%b✗ %s%b\n" "$RED" "$1" "$NC"; }

# ---- Banner --------------------------------------------------------------
printf "\n"
printf "%b================================================%b\n" "$BOLD" "$NC"
printf "%b  Plaud Meetings Digest — Installer%b\n" "$BOLD" "$NC"
printf "%b  by Gallant Solutions%b\n" "$BOLD" "$NC"
printf "%b================================================%b\n\n" "$BOLD" "$NC"

# ---- Resolve paths -------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_MEETINGS_SRC="$SCRIPT_DIR/skills/meetings-digest"
SKILL_ROLLUP_SRC="$SCRIPT_DIR/skills/weekly-rollup"
SCRIPTS_SRC="$SCRIPT_DIR/scripts"
CONFIG_SRC="$SCRIPT_DIR/config/digest-config.template.json"

SKILL_MEETINGS_INSTALL="$HOME/.claude/skills/meetings-digest"
SKILL_ROLLUP_INSTALL="$HOME/.claude/skills/weekly-rollup"
SCRIPTS_INSTALL="$SKILL_MEETINGS_INSTALL/scripts"
CONFIG_INSTALL="$SKILL_MEETINGS_INSTALL/config.json"

# ============================================================================
# Step 1 — Prerequisite check
# ============================================================================
say "Step 1/6 — Checking prerequisites"

MISSING=()
INSTALL_HINTS=""

check_macos() {
  if [[ "$OSTYPE" != darwin* ]]; then
    err "install.sh is Mac-only. Detected: $OSTYPE"
    printf "  On Windows, paste this in PowerShell instead:\n"
    printf "    %biwr -useb https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.ps1 | iex%b\n" "$BLUE" "$NC"
    exit 1
  fi
  ok "macOS detected"
}

check_xcode_clt() {
  if ! xcode-select -p &>/dev/null; then
    MISSING+=("Xcode Command Line Tools")
    INSTALL_HINTS+="  Xcode CLT:     xcode-select --install  (popup → click Install; takes 5–15 min)\n"
  else
    ok "Xcode Command Line Tools present"
  fi
}

check_brew() {
  if ! command -v brew &>/dev/null; then
    MISSING+=("Homebrew")
    INSTALL_HINTS+='  Homebrew:      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"\n'
  else
    ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"
  fi
}

check_node() {
  if ! command -v node &>/dev/null; then
    MISSING+=("Node.js 20+")
    INSTALL_HINTS+="  Node 20:       brew install node@20 && brew link --overwrite node@20\n"
    return
  fi
  local major
  major=$(node -v | sed 's/v//' | cut -d. -f1)
  if (( major < 20 )); then
    MISSING+=("Node.js 20+ (found v$major)")
    INSTALL_HINTS+="  Node 20:       brew install node@20 && brew link --overwrite node@20\n"
  else
    ok "Node.js $(node -v)"
  fi
}

check_claude_code() {
  if ! command -v claude &>/dev/null; then
    MISSING+=("Claude Code CLI")
    INSTALL_HINTS+="  Claude Code:   brew install --cask claude-code\n"
    INSTALL_HINTS+="                 (or download from https://claude.ai/code/install)\n"
  else
    ok "Claude Code CLI: $(command -v claude)"
  fi
}

check_python() {
  if ! command -v python3 &>/dev/null; then
    MISSING+=("Python 3")
    INSTALL_HINTS+="  Python 3:      brew install python@3.11\n"
  else
    ok "Python $(python3 --version | awk '{print $2}')"
  fi
}

check_macos
check_xcode_clt
check_brew
check_node
check_claude_code
check_python

if (( ${#MISSING[@]} > 0 )); then
  printf "\n"
  err "Missing prerequisites: ${MISSING[*]}"
  printf "\nInstall commands:\n"
  printf "%b$INSTALL_HINTS%b\n" "$YELLOW" "$NC"
  printf "Re-run %b./install.sh%b after installing the above.\n\n" "$BOLD" "$NC"
  exit 1
fi

ok "All prerequisites present"

# ============================================================================
# Step 2 — Install Plaud MCP server
# ============================================================================
printf "\n"
say "Step 2/6 — Installing Plaud MCP server"
printf "\n"
printf "%bThis step opens a browser for Plaud OAuth.%b\n" "$YELLOW" "$NC"
printf "Sign into your Plaud account and click %bAuthorize%b when prompted.\n\n" "$BOLD" "$NC"
read -p "Press Enter to continue (or Ctrl+C to abort)... "

if npx -y "@plaud-ai/mcp@latest" install; then
  ok "Plaud MCP installed and authorized"
else
  err "Plaud MCP install failed. See output above for details."
  printf "Re-run %b./install.sh%b once resolved.\n" "$BOLD" "$NC"
  exit 1
fi

# ============================================================================
# Step 3 — Python dependencies
# ============================================================================
printf "\n"
say "Step 3/6 — Installing Python dependencies (requests)"

install_python_pkg() {
  local pkg="$1"
  if python3 -c "import $2" &>/dev/null; then
    ok "$pkg already installed"
    return
  fi
  if python3 -m pip install --quiet --user "$pkg"; then
    ok "$pkg installed"
  elif python3 -m pip install --quiet --user --break-system-packages "$pkg"; then
    ok "$pkg installed (with --break-system-packages)"
  else
    err "Could not install $pkg. Try manually: python3 -m pip install $pkg"
    exit 1
  fi
}

install_python_pkg "requests"     "requests"
install_python_pkg "python-docx"  "docx"

# ============================================================================
# Step 4 — Configure output destination + meeting routing
# ============================================================================
printf "\n"
say "Step 4/7 — Choose output destination"
printf "\n"
printf "Where should meeting outputs be written? (Mac default is Notion.)\n\n"
printf "  %b1)%b Notion — action items into a Notion database (recommended on Mac)\n" "$BOLD" "$NC"
printf "  %b2)%b Folder — markdown files at ~/Plaud-Digests/<week>.md (no setup, universal fallback)\n\n" "$BOLD" "$NC"

DEST_CHOICE=""
while [[ "$DEST_CHOICE" != "1" && "$DEST_CHOICE" != "2" ]]; do
  read -p "Choice [1 or 2, default 1]: " DEST_CHOICE
  DEST_CHOICE="${DEST_CHOICE:-1}"
done
# Swap so that 1 = notion, 2 = folder (matches the prompt order)
if [[ "$DEST_CHOICE" == "1" ]]; then DEST_CHOICE="notion"; else DEST_CHOICE="folder"; fi

DEST_TYPE=""
DEST_FOLDER=""
NOTION_API_KEY=""
NOTION_DATABASE_ID=""
NOTION_PARENT_PAGE_ID=""

if [[ "$DEST_CHOICE" == "folder" ]]; then
  DEST_TYPE="folder"
  printf "\n"
  read -p "Folder path [default ~/Plaud-Digests]: " DEST_FOLDER
  DEST_FOLDER="${DEST_FOLDER:-$HOME/Plaud-Digests}"
  DEST_FOLDER="${DEST_FOLDER/#\~/$HOME}"
  mkdir -p "$DEST_FOLDER"
  ok "Folder destination: $DEST_FOLDER"
else
  DEST_TYPE="notion"
  printf "\n"
  printf "%bNotion setup:%b\n" "$BOLD" "$NC"
  printf "  1. Visit %bhttps://www.notion.so/my-integrations%b\n" "$BLUE" "$NC"
  printf "  2. Click %b+ New integration%b — name it %b\"Plaud Meeting Digest\"%b\n" "$BOLD" "$NC" "$BOLD" "$NC"
  printf "  3. Associate it with your workspace and copy the %bInternal Integration Token%b (starts with %bsecret_%b or %bntn_%b)\n" "$BOLD" "$NC" "$BOLD" "$NC" "$BOLD" "$NC"
  printf "  4. Open the Notion page where the meeting-digest database should live\n"
  printf "  5. Click the %b…%b menu (top right) → %bConnect to%b → select your new integration\n" "$BOLD" "$NC" "$BOLD" "$NC"
  printf "  6. Copy that page's ID from the URL (the 32-char hex string after the page title)\n\n"

  read -p "Paste your Notion Integration Token: " NOTION_API_KEY
  read -p "Paste the parent page ID (32-char hex, dashes optional): " NOTION_PARENT_PAGE_ID

  # Strip dashes from page ID for consistency
  NOTION_PARENT_PAGE_ID="${NOTION_PARENT_PAGE_ID//-/}"

  printf "\n"
  say "Creating Notion database via API..."
  if python3 "$SCRIPTS_SRC/notion-setup.py" \
      --token "$NOTION_API_KEY" \
      --parent-page "$NOTION_PARENT_PAGE_ID" \
      --output "$SCRIPT_DIR/.notion-db-id.tmp"; then
    NOTION_DATABASE_ID=$(cat "$SCRIPT_DIR/.notion-db-id.tmp")
    rm -f "$SCRIPT_DIR/.notion-db-id.tmp"
    ok "Notion database created (ID: ${NOTION_DATABASE_ID:0:8}...)"
    ok "Parent page bound for weekly rollup pages (ID: ${NOTION_PARENT_PAGE_ID:0:8}...)"
  else
    err "Notion database creation failed. See above for details."
    err "Common causes: token has no access to the parent page, page ID wrong."
    exit 1
  fi
fi

# ============================================================================
# Step 5 — Meeting routing
# ============================================================================
printf "\n"
say "Step 5/7 — Configure meeting routing"
printf "\n"
printf "When the client starts each Plaud recording, they state the meeting type\n"
printf "(e.g., 'Kingsway Pharma meeting with John Smith'). The skill matches the\n"
printf "spoken opening line against keywords to route to the right folder/group.\n\n"
printf "Default meeting types:\n"
printf "  • Kingsway Pharma   → folder 'Kingsway Pharma'   → 'KPM' (meetings) + 'KPR' (rollup)  → per-week subfolders → INCLUDED in Friday rollup\n"
printf "  • Committee         → folder 'Committee'         → 'CMM' (meetings) + 'CMR' (rollup)  → per-week subfolders → INCLUDED in Friday rollup\n"
printf "  • Church            → folder 'Church'            → 'CHM' (meetings) + 'CHR' (rollup)  → per-week subfolders → INCLUDED in Friday rollup\n"
printf "  • Personal          → folder 'Personal'          → 'PM'  (meetings) + 'PR'  (rollup)  → per-week subfolders → INCLUDED in Friday rollup\n\n"
printf "  Files land as: {prefix}.{short topic} ({attendees}).docx\n"
printf "    e.g. Kingsway Pharma/KPM.May 25-29, 2026 (Week 22)/KPM.Q3 Plans (John Smith).docx\n"
printf "    rollup: Kingsway Pharma/KPM.May 25-29, 2026 (Week 22)/KPR.May 25-29, 2026 (Week 22).docx\n\n"
read -p "Use these defaults? [Y/n]: " ROUTING_CHOICE
ROUTING_CHOICE="${ROUTING_CHOICE:-Y}"

ROUTING_JSON='[
  { "keyword": "Kingsway Pharma", "folder": "Kingsway Pharma", "filename_prefix": "KPM", "rollup_filename_prefix": "KPR", "weekly_subfolders": true, "include_in_weekly_rollup": true },
  { "keyword": "Committee",       "folder": "Committee",       "filename_prefix": "CMM", "rollup_filename_prefix": "CMR", "weekly_subfolders": true, "include_in_weekly_rollup": true },
  { "keyword": "Church",          "folder": "Church",          "filename_prefix": "CHM", "rollup_filename_prefix": "CHR", "weekly_subfolders": true, "include_in_weekly_rollup": true },
  { "keyword": "Personal",        "folder": "Personal",        "filename_prefix": "PM",  "rollup_filename_prefix": "PR",  "weekly_subfolders": true, "include_in_weekly_rollup": true }
]'

if [[ "$ROUTING_CHOICE" =~ ^[Nn]$ ]]; then
  printf "\nEnter meeting types one per line, 6 pipe-separated fields:\n"
  printf "  keyword|folder|filename_prefix|rollup_filename_prefix_or_none|weekly_subfolders(yes/no)|include_in_rollup(yes/no)\n"
  printf "Example: Kingsway Pharma|Kingsway Pharma|KPM|KPR|yes|yes\n"
  printf "Example: Personal|Personal|PM|none|no|no\n"
  printf "Blank line to finish.\n\n"
  ITEMS="["
  FIRST=1
  while true; do
    read -p "Meeting type: " LINE
    if [[ -z "$LINE" ]]; then break; fi
    IFS='|' read -ra PARTS <<< "$LINE"
    if [[ ${#PARTS[@]} -ne 6 ]]; then warn "Need 6 pipe-separated fields"; continue; fi
    KW="${PARTS[0]}"
    FOLDER="${PARTS[1]}"
    PREFIX="${PARTS[2]}"
    ROLLUP_PREFIX="${PARTS[3]}"
    WEEKLY_SUB="${PARTS[4]}"
    INCL="${PARTS[5]}"
    if [[ "$ROLLUP_PREFIX" == "none" || -z "$ROLLUP_PREFIX" ]]; then ROLLUP_PREFIX_JSON="null"; else ROLLUP_PREFIX_JSON="\"$ROLLUP_PREFIX\""; fi
    if [[ "$WEEKLY_SUB" == "yes" ]]; then WEEKLY_BOOL="true"; else WEEKLY_BOOL="false"; fi
    if [[ "$INCL" == "yes" ]]; then INCL_BOOL="true"; else INCL_BOOL="false"; fi
    if [[ $FIRST -eq 0 ]]; then ITEMS+=","; fi
    ITEMS+=$(printf '\n  {"keyword":"%s","folder":"%s","filename_prefix":"%s","rollup_filename_prefix":%s,"weekly_subfolders":%s,"include_in_weekly_rollup":%s}' "$KW" "$FOLDER" "$PREFIX" "$ROLLUP_PREFIX_JSON" "$WEEKLY_BOOL" "$INCL_BOOL")
    FIRST=0
  done
  ITEMS+="\n]"
  ROUTING_JSON="$ITEMS"
fi
ok "Meeting routing configured"

# ============================================================================
# Step 5b — Heartbeat (Gallant operator telemetry)
# ============================================================================
printf "\n"
say "Step 5b/7 — Heartbeat (operator alerts when something breaks)"
printf "\n"
printf "Gallant uses Healthchecks.io to alert the operator if a scheduled run\n"
printf "doesn't complete on time. Setup runbook: OPERATOR-INSTALL-GUIDE.md.\n\n"

HEARTBEAT_ENABLED="false"
HEARTBEAT_BASE="${GALLANT_HEARTBEAT_BASE:-https://hc-ping.com}"
CHECK_LUNCH="${GALLANT_HEARTBEAT_CHECK_LUNCH:-}"
CHECK_EOD="${GALLANT_HEARTBEAT_CHECK_EOD:-}"
CHECK_ROLLUP="${GALLANT_HEARTBEAT_CHECK_ROLLUP:-}"
CHECK_AUTO_UPDATE="${GALLANT_HEARTBEAT_CHECK_AUTO_UPDATE:-}"

ENV_PROVIDED=""
if [[ -n "$CHECK_LUNCH$CHECK_EOD$CHECK_ROLLUP$CHECK_AUTO_UPDATE" ]]; then ENV_PROVIDED="yes"; fi

if [[ -z "$ENV_PROVIDED" ]]; then
  read -p "Enable heartbeat? [Y/n]: " HB_ENABLE
  HB_ENABLE="${HB_ENABLE:-Y}"
  if [[ "$HB_ENABLE" =~ ^[Yy]$ ]]; then
    read -p "Ping base URL [default https://hc-ping.com]: " HB_BASE_IN
    if [[ -n "$HB_BASE_IN" ]]; then HEARTBEAT_BASE="$HB_BASE_IN"; fi
    read -p "Check UUID for daily 11:00 AM (lunch): " CHECK_LUNCH
    read -p "Check UUID for daily 4:00 PM (eod): " CHECK_EOD
    read -p "Check UUID for Friday 4:30 PM (rollup): " CHECK_ROLLUP
    read -p "Check UUID for daily 3:00 AM (auto-update): " CHECK_AUTO_UPDATE
  fi
fi

if [[ -n "$CHECK_LUNCH$CHECK_EOD$CHECK_ROLLUP$CHECK_AUTO_UPDATE" ]]; then
  HEARTBEAT_ENABLED="true"
  ok "Heartbeat enabled"
else
  warn "Heartbeat skipped — operator gets no alerts when jobs fail silently"
fi

# ============================================================================
# Step 6 — Install skills + scripts + config
# ============================================================================
printf "\n"
say "Step 6/7 — Installing skills into Claude Code"

mkdir -p "$SKILL_MEETINGS_INSTALL"
mkdir -p "$SKILL_ROLLUP_INSTALL"
mkdir -p "$SCRIPTS_INSTALL"

cp "$SKILL_MEETINGS_SRC/SKILL.md" "$SKILL_MEETINGS_INSTALL/SKILL.md"
cp "$SKILL_ROLLUP_SRC/SKILL.md"   "$SKILL_ROLLUP_INSTALL/SKILL.md"
# Copy ALL python helpers (Notion + Word/OneDrive + state-store + onedrive-resolve + runner + tray_bridge)
cp "$SCRIPTS_SRC"/*.py "$SCRIPTS_INSTALL/"
chmod +x "$SCRIPTS_INSTALL"/*.py

# Tray subpackage — required because tray_bridge.py imports `from tray import state`.
# The tray widget itself is Windows-only (pywebview + pystray), but the bridge runs
# on whichever host fires the weekly rollup, so the package must be installed here too.
TRAY_PKG_SRC="$SCRIPTS_SRC/tray"
TRAY_PKG_DEST="$SCRIPTS_INSTALL/tray"
if [[ -d "$TRAY_PKG_SRC" ]]; then
  rm -rf "$TRAY_PKG_DEST"
  mkdir -p "$TRAY_PKG_DEST"
  # rsync gives us clean excludes for dev artifacts; fall back to cp + find if absent.
  if command -v rsync &>/dev/null; then
    rsync -a \
      --exclude='preview.html' \
      --exclude='README.md' \
      --exclude='install_tray.ps1' \
      --exclude='__pycache__' \
      "$TRAY_PKG_SRC/" "$TRAY_PKG_DEST/"
  else
    cp -R "$TRAY_PKG_SRC/." "$TRAY_PKG_DEST/"
    rm -f "$TRAY_PKG_DEST/preview.html" "$TRAY_PKG_DEST/README.md" "$TRAY_PKG_DEST/install_tray.ps1"
    find "$TRAY_PKG_DEST" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
  fi
  ok "Tray subpackage installed at $TRAY_PKG_DEST"
fi

mkdir -p "$SKILL_MEETINGS_INSTALL/state"

# Build config.json from template
python3 - <<EOF
import json
from pathlib import Path

template = json.loads(Path("$CONFIG_SRC").read_text())
template["installed_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
template["platform"] = "macos"
template["destination"]["type"] = "$DEST_TYPE"
template["destination"]["folder"] = "$DEST_FOLDER" if "$DEST_TYPE" == "folder" else None
template["destination"]["notion_api_key"] = "$NOTION_API_KEY" if "$DEST_TYPE" == "notion" else None
template["destination"]["notion_database_id"] = "$NOTION_DATABASE_ID" if "$DEST_TYPE" == "notion" else None
template["destination"]["notion_parent_page_id"] = "$NOTION_PARENT_PAGE_ID" if "$DEST_TYPE" == "notion" else None

# Meeting routing overrides
template["meeting_routing"]["types"] = json.loads('''$ROUTING_JSON''')

# Heartbeat block (operator-supplied at install time)
template["gallant_heartbeat"]["enabled"] = "$HEARTBEAT_ENABLED" == "true"
template["gallant_heartbeat"]["ping_base_url"] = "$HEARTBEAT_BASE"
template["gallant_heartbeat"]["checks"]["lunch"]       = "$CHECK_LUNCH" or None
template["gallant_heartbeat"]["checks"]["eod"]         = "$CHECK_EOD" or None
template["gallant_heartbeat"]["checks"]["rollup"]      = "$CHECK_ROLLUP" or None
template["gallant_heartbeat"]["checks"]["auto_update"] = "$CHECK_AUTO_UPDATE" or None

Path("$CONFIG_INSTALL").write_text(json.dumps(template, indent=2))
EOF

chmod 600 "$CONFIG_INSTALL"  # protect Notion API key
ok "Skills installed at $SKILL_MEETINGS_INSTALL and $SKILL_ROLLUP_INSTALL"
ok "Config written (mode 600 — Notion key protected)"

# Write version stamp (for auto-update version comparison)
BUNDLE_PREFIX="$SCRIPT_DIR"
BUNDLE_VERSION=$(python3 -c "import json; print(json.loads(open('$CONFIG_SRC').read())['version'])")
echo "$BUNDLE_VERSION" > "$BUNDLE_PREFIX/version.txt"
ok "Bundle version stamped: $BUNDLE_VERSION -> $BUNDLE_PREFIX/version.txt"

# ============================================================================
# Step 6d — Playwright readiness (v2.5.0)
# ============================================================================
# Infrastructure-only ship. Default config has plaud.method = "mcp_only" so the
# install behavior is unchanged. To enable Plaud's Export-tier Summary fetch:
#   1. pip3 install playwright && python3 -m playwright install chromium
#   2. python3 scripts/plaud_playwright.py --check-session   # interactive auth on first run
#   3. Edit ~/.claude/skills/meetings-digest/config.json — set plaud.method = "auto"
# (Mac doesn't ship playwright_setup.ps1 — Garrett uses the kit interactively via
# `playwright codegen https://web.plaud.ai/` for selector verification on his own
# Plaud account. Once selectors verify, ship the config flip to clients.)
PW_RUNNER="$SCRIPTS_SRC/plaud_playwright_runner.py"
if [[ -f "$PW_RUNNER" ]]; then
  ok "Playwright runner at $PW_RUNNER (disabled by default — set plaud.method = \"auto\" to enable)"
else
  echo "  ⚠ plaud_playwright_runner.py missing — Playwright upgrade path unavailable"
fi

# ============================================================================
# Step 7 — Schedule (lunch + EOD + Friday rollup)
# ============================================================================
printf "\n"
say "Step 7/7 — Schedule three jobs"
printf "\n"
printf "This will install three launchd jobs:\n"
printf "  • Daily 11:00 AM — lunch meetings pull\n"
printf "  • Daily  4:00 PM — afternoon meetings pull\n"
printf "  • Friday 4:30 PM — weekly rollup (Kingsway Pharma + Committee)\n\n"
read -p "Enable schedule? [Y/n]: " SCHEDULE_CHOICE
SCHEDULE_CHOICE="${SCHEDULE_CHOICE:-Y}"

SCHEDULE_CHOICE="${SCHEDULE_CHOICE:-Y}"
if [[ "$SCHEDULE_CHOICE" =~ ^[Yy]$ ]]; then
  if bash "$SCRIPT_DIR/scripts/schedule.sh"; then
    ok "Schedule installed (lunch + EOD + Friday rollup)"
  else
    warn "Schedule install failed. You can re-run scripts/schedule.sh later."
  fi
else
  printf "Skipped. You can install scheduling later via %bscripts/schedule.sh%b.\n" "$BOLD" "$NC"
fi

# ============================================================================
# Done
# ============================================================================
printf "\n"
printf "%b================================================%b\n" "$GREEN" "$NC"
printf "%b✓ Installation complete%b\n" "$GREEN" "$NC"
printf "%b================================================%b\n\n" "$GREEN" "$NC"

printf "%bWhat's next:%b\n\n" "$BOLD" "$NC"
printf "  • Test it now:    %bclaude -p \"/meetings-digest\"%b\n" "$BOLD" "$NC"
printf "  • Interactive:    %bclaude%b → then type %b/meetings-digest%b\n" "$BOLD" "$NC" "$BOLD" "$NC"
if [[ "$SCHEDULE_CHOICE" =~ ^[Yy]$ ]]; then
  printf "  • Scheduled:      Lunch 11:00 AM, EOD 4:00 PM daily; Friday 4:30 PM rollup.\n"
  printf "                    Logs: ~/Library/Logs/plaud-meetings-digest.log\n"
fi
printf "\n%bTrain the client:%b tell them to ALWAYS state the meeting type at the start of every Plaud recording\n" "$BOLD" "$NC"
printf "(e.g., 'Kingsway Pharma meeting with John Smith'). Without this, recordings route to 'Uncategorized'.\n"
if [[ "$DEST_TYPE" == "folder" ]]; then
  printf "  • Digest files:   %s/\n" "$DEST_FOLDER"
else
  printf "  • Digest items:   Open your Notion workspace; check the 'Plaud Meeting Action Items' database\n"
fi
printf "\nTo remove: run %b./uninstall.sh%b from this folder.\n\n" "$BOLD" "$NC"
