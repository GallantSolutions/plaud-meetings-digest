#!/usr/bin/env bash
# ============================================================================
# Plaud Meetings Digest — One-Line Bootstrap Installer
# ============================================================================
#
# Recipient runs this single command (operator pastes for them):
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)
#
# This script:
#   1. Resolves the latest release tag from the GitHub repo
#   2. Downloads + extracts the release tarball to ~/Library/Application Support/plaud-meetings-digest
#   3. Chains into install.sh which handles prereq checks + Plaud OAuth +
#      Notion setup + skill install + Friday schedule
#
# Overrides via environment variables:
#   PLAUD_DIGEST_REPO     — GitHub <owner>/<repo>           (default: GallantSolutions/plaud-meetings-digest)
#   PLAUD_DIGEST_VERSION  — Release tag or "main"           (default: latest released tag, fallback to main)
#   PLAUD_DIGEST_PREFIX   — Where to install the bundle    (default: ~/Library/Application Support/plaud-meetings-digest)
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

say()  { printf "%b→ %s%b\n" "$BLUE" "$1" "$NC"; }
ok()   { printf "%b✓ %s%b\n" "$GREEN" "$1" "$NC"; }
warn() { printf "%b⚠ %s%b\n" "$YELLOW" "$1" "$NC"; }
err()  { printf "%b✗ %s%b\n" "$RED" "$1" "$NC"; }

# ---- Defaults --------------------------------------------------------------
REPO="${PLAUD_DIGEST_REPO:-GallantSolutions/plaud-meetings-digest}"
VERSION="${PLAUD_DIGEST_VERSION:-latest}"
INSTALL_DIR="${PLAUD_DIGEST_PREFIX:-$HOME/Library/Application Support/plaud-meetings-digest}"

# ---- OS guard: refuse to run on non-Mac -----------------------------------
# bash runs on Linux + WSL too. If pasted on Windows (via WSL or similar),
# redirect to the PowerShell one-liner — that's the supported Windows path.
if [[ "$OSTYPE" != darwin* ]]; then
  err "This is the Mac bootstrap, but you're on $OSTYPE."
  printf "\n"
  printf "%bRun this Windows one-liner instead (paste into PowerShell, not bash):%b\n\n" "$YELLOW" "$NC"
  printf "%b  iwr -useb https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.ps1 | iex%b\n\n" "$BLUE" "$NC"
  exit 1
fi

if ! command -v curl &>/dev/null; then
  err "curl not found. (This shouldn't happen on macOS — install Xcode CLT first: xcode-select --install)"
  exit 1
fi

if ! command -v tar &>/dev/null; then
  err "tar not found. Install Xcode CLT: xcode-select --install"
  exit 1
fi

# ---- Banner ----------------------------------------------------------------
printf "\n"
printf "%b===========================================================%b\n" "$BOLD" "$NC"
printf "%b  Plaud Meetings Digest — Bootstrap Installer%b\n" "$BOLD" "$NC"
printf "%b  Repo: %s%b\n" "$BOLD" "$REPO" "$NC"
printf "%b===========================================================%b\n\n" "$BOLD" "$NC"

# ---- Resolve version -------------------------------------------------------
if [[ "$VERSION" == "latest" ]]; then
  say "Resolving latest release tag from GitHub..."
  # Try the releases/latest API. If no releases yet, fall back to main.
  if command -v python3 &>/dev/null; then
    VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
      | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('tag_name',''))" 2>/dev/null || true)
  else
    # Plain grep/sed fallback if python3 isn't installed yet (unlikely on macOS but possible)
    VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
      | grep '"tag_name":' | head -1 | sed -E 's/.*"tag_name":[[:space:]]*"([^"]+)".*/\1/' || true)
  fi
  if [[ -z "${VERSION:-}" ]]; then
    warn "No tagged release found; using main branch."
    VERSION="main"
  else
    ok "Latest release: $VERSION"
  fi
fi

# ---- Download tarball ------------------------------------------------------
TMPDIR=$(mktemp -d -t plaud-digest)
trap 'rm -rf "$TMPDIR"' EXIT

if [[ "$VERSION" == "main" ]]; then
  TARBALL_URL="https://github.com/$REPO/archive/refs/heads/main.tar.gz"
else
  TARBALL_URL="https://github.com/$REPO/archive/refs/tags/$VERSION.tar.gz"
fi

say "Downloading $TARBALL_URL"
if ! curl -fsSL --retry 3 "$TARBALL_URL" -o "$TMPDIR/plaud.tar.gz"; then
  err "Download failed. Check the repo name + version + internet connection."
  err "Repo:    https://github.com/$REPO"
  err "Version: $VERSION"
  exit 1
fi
ok "Downloaded $(du -h "$TMPDIR/plaud.tar.gz" | awk '{print $1}')"

say "Extracting..."
tar -xzf "$TMPDIR/plaud.tar.gz" -C "$TMPDIR"

# GitHub renames the extracted dir to <repo>-<branch-or-tag-without-v-prefix>
EXTRACTED=$(find "$TMPDIR" -maxdepth 1 -type d -name "plaud-meetings-digest*" | head -1)
if [[ -z "$EXTRACTED" ]]; then
  err "Extraction failed — no extracted directory found."
  exit 1
fi
ok "Extracted to $(basename "$EXTRACTED")"

# ---- Install to canonical location -----------------------------------------
say "Installing to $INSTALL_DIR"
if [[ -d "$INSTALL_DIR" ]]; then
  warn "Existing install found — replacing."
  rm -rf "$INSTALL_DIR"
fi
mkdir -p "$(dirname "$INSTALL_DIR")"
mv "$EXTRACTED" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/install.sh" "$INSTALL_DIR/uninstall.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/scripts/"*.sh "$INSTALL_DIR/scripts/"*.py 2>/dev/null || true
ok "Bundle landed at $INSTALL_DIR"

# ---- Chain into install.sh -------------------------------------------------
printf "\n"
say "Launching install.sh (will walk through prereqs, Plaud OAuth, Notion setup, schedule)"
printf "\n"
cd "$INSTALL_DIR"
exec ./install.sh
