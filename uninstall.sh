#!/usr/bin/env bash
# ============================================================================
# Plaud Meetings Digest — Uninstaller
# ============================================================================
# Removes the meetings-digest + weekly-rollup skills, scheduled job(s), and
# config. Does NOT uninstall Plaud MCP (you may use it for other things) or
# Claude Code itself. Does NOT delete past digest files in your output folder
# or your Notion database.
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { printf "%b✓ %s%b\n" "$GREEN" "$1" "$NC"; }
warn() { printf "%b⚠ %s%b\n" "$YELLOW" "$1" "$NC"; }

printf "\n%bPlaud Meetings Digest — Uninstaller%b\n\n" "$BOLD" "$NC"

# Remove scheduled jobs (current v2.0.0 + all legacy variants)
REMOVED_ANY=false
for PLIST in \
  "$HOME/Library/LaunchAgents/com.gallant.plaud-meetings-digest.lunch.plist" \
  "$HOME/Library/LaunchAgents/com.gallant.plaud-meetings-digest.eod.plist" \
  "$HOME/Library/LaunchAgents/com.gallant.plaud-meetings-digest.rollup.plist" \
  "$HOME/Library/LaunchAgents/com.gallant.plaud-meetings-digest.friday-rollup.plist" \
  "$HOME/Library/LaunchAgents/com.gallant.plaud-meetings-digest.weekly-rollup.plist" \
  "$HOME/Library/LaunchAgents/com.gallant.plaud-meetings-digest.plist"; do
  if [[ -f "$PLIST" ]]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    ok "Scheduled job removed: $(basename "$PLIST")"
    REMOVED_ANY=true
  fi
done
if [[ "$REMOVED_ANY" == "false" ]]; then
  warn "No scheduled jobs found (skipped)"
fi

# Remove skills + scripts + config
for SKILL_DIR in \
  "$HOME/.claude/skills/meetings-digest" \
  "$HOME/.claude/skills/weekly-rollup"; do
  if [[ -d "$SKILL_DIR" ]]; then
    rm -rf "$SKILL_DIR"
    ok "Skill removed from $SKILL_DIR"
  else
    warn "Skill not found at $SKILL_DIR (skipped)"
  fi
done

# Optional: remove Plaud MCP from Claude Code config
read -p "Also remove Plaud MCP from Claude Code? [y/N]: " REMOVE_MCP
if [[ "$REMOVE_MCP" =~ ^[Yy]$ ]]; then
  if claude mcp remove plaud 2>/dev/null; then
    ok "Plaud MCP removed from Claude Code"
  else
    warn "Could not remove Plaud MCP automatically. Edit ~/.claude/mcp.json manually if needed."
  fi
else
  printf "Plaud MCP left in place (you can still use it).\n"
fi

printf "\n%b✓ Uninstalled.%b\n" "$GREEN" "$NC"
printf "Past digests left untouched in your output folder.\n"
printf "Notion database (if used) left in your workspace.\n\n"
