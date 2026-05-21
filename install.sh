#!/usr/bin/env bash
# ============================================================================
# Plaud Meetings Digest — Installer
# ============================================================================
# Installs the meetings-digest + weekly-rollup skills into Claude Code, wires
# up the Plaud MCP server, configures the output destination (folder or Notion),
# and optionally schedules the Friday 5:00 PM weekly rollup.
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
    err "This installer is macOS-only. Detected: $OSTYPE"
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

if python3 -c "import requests" &>/dev/null; then
  ok "requests already installed"
else
  if python3 -m pip install --quiet --user requests; then
    ok "requests installed"
  elif python3 -m pip install --quiet --user --break-system-packages requests; then
    ok "requests installed (with --break-system-packages)"
  else
    err "Could not install requests. Try manually: python3 -m pip install requests"
    exit 1
  fi
fi

# ============================================================================
# Step 4 — Configure output destination
# ============================================================================
printf "\n"
say "Step 4/6 — Choose output destination"
printf "\n"
printf "Where should weekly meeting digests be written?\n\n"
printf "  %b1)%b Folder — markdown files at ~/Plaud-Digests/<week>.md (no setup, opens in any editor)\n" "$BOLD" "$NC"
printf "  %b2)%b Notion — action items into a Notion database (you'll provide API key + page ID)\n\n" "$BOLD" "$NC"

DEST_CHOICE=""
while [[ "$DEST_CHOICE" != "1" && "$DEST_CHOICE" != "2" ]]; do
  read -p "Choice [1 or 2]: " DEST_CHOICE
done

DEST_TYPE=""
DEST_FOLDER=""
NOTION_API_KEY=""
NOTION_DATABASE_ID=""
NOTION_PARENT_PAGE_ID=""

if [[ "$DEST_CHOICE" == "1" ]]; then
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
# Step 5 — Install skills + scripts + config
# ============================================================================
printf "\n"
say "Step 5/6 — Installing skills into Claude Code"

mkdir -p "$SKILL_MEETINGS_INSTALL"
mkdir -p "$SKILL_ROLLUP_INSTALL"
mkdir -p "$SCRIPTS_INSTALL"

cp "$SKILL_MEETINGS_SRC/SKILL.md" "$SKILL_MEETINGS_INSTALL/SKILL.md"
cp "$SKILL_ROLLUP_SRC/SKILL.md"   "$SKILL_ROLLUP_INSTALL/SKILL.md"
cp "$SCRIPTS_SRC/notion-write.py"      "$SCRIPTS_INSTALL/notion-write.py"
cp "$SCRIPTS_SRC/notion-query.py"      "$SCRIPTS_INSTALL/notion-query.py"
cp "$SCRIPTS_SRC/notion-page-write.py" "$SCRIPTS_INSTALL/notion-page-write.py"
cp "$SCRIPTS_SRC/digest-runner.py"     "$SCRIPTS_INSTALL/digest-runner.py"
chmod +x "$SCRIPTS_INSTALL"/*.py

# Build config.json from template
python3 - <<EOF
import json
from pathlib import Path

template = json.loads(Path("$CONFIG_SRC").read_text())
template["destination"]["type"] = "$DEST_TYPE"
template["destination"]["folder"] = "$DEST_FOLDER" if "$DEST_TYPE" == "folder" else None
template["destination"]["notion_api_key"] = "$NOTION_API_KEY" if "$DEST_TYPE" == "notion" else None
template["destination"]["notion_database_id"] = "$NOTION_DATABASE_ID" if "$DEST_TYPE" == "notion" else None
template["destination"]["notion_parent_page_id"] = "$NOTION_PARENT_PAGE_ID" if "$DEST_TYPE" == "notion" else None
template["installed_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

Path("$CONFIG_INSTALL").write_text(json.dumps(template, indent=2))
EOF

chmod 600 "$CONFIG_INSTALL"  # protect Notion API key
ok "Skills installed at $SKILL_MEETINGS_INSTALL and $SKILL_ROLLUP_INSTALL"
ok "Config written (mode 600 — Notion key protected)"

# ============================================================================
# Step 6 — Optional Friday weekly rollup schedule
# ============================================================================
printf "\n"
say "Step 6/6 — Optional Friday weekly rollup schedule"
printf "\n"
printf "Set up automatic Friday weekly rollup?\n"
printf "  • Fires every Friday at 5:00 PM local time\n"
printf "  • Pulls the week's Plaud meetings, extracts action items into Notion\n"
printf "  • Synthesizes a 'Week of …' rollup page so the user has it for weekend reflection\n\n"
read -p "Enable Friday weekly rollup schedule? [Y/n]: " SCHEDULE_CHOICE
SCHEDULE_CHOICE="${SCHEDULE_CHOICE:-Y}"

if [[ "$SCHEDULE_CHOICE" =~ ^[Yy]$ ]]; then
  if bash "$SCRIPT_DIR/scripts/schedule.sh"; then
    ok "Friday weekly rollup schedule installed"
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
  printf "  • Scheduled:      Friday 5:00 PM local — pulls week + writes rollup.\n"
  printf "                    Next-run logs: ~/Library/Logs/plaud-meetings-digest.log\n"
fi
if [[ "$DEST_TYPE" == "folder" ]]; then
  printf "  • Digest files:   %s/\n" "$DEST_FOLDER"
else
  printf "  • Digest items:   Open your Notion workspace; check the 'Plaud Meeting Action Items' database\n"
fi
printf "\nTo remove: run %b./uninstall.sh%b from this folder.\n\n" "$BOLD" "$NC"
