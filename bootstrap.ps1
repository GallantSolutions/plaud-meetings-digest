# ============================================================================
# Plaud Meetings Digest — Windows One-Line Bootstrap
# ============================================================================
#
# Recipient runs this single command in PowerShell (operator pastes for them):
#
#   iwr -useb https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.ps1 | iex
#
# This script:
#   1. Resolves the latest release tag from the GitHub repo
#   2. Downloads + extracts the release zip into %LOCALAPPDATA%\plaud-meetings-digest
#   3. Chains into install.ps1 which handles prereqs + Plaud OAuth + OneDrive +
#      meeting routing + Windows Task Scheduler jobs
#
# Overrides via env vars:
#   $env:PLAUD_DIGEST_REPO    — owner/repo                (default: GallantSolutions/plaud-meetings-digest)
#   $env:PLAUD_DIGEST_VERSION — tag or "main"            (default: latest released tag, fallback to main)
#   $env:PLAUD_DIGEST_PREFIX  — install location          (default: %LOCALAPPDATA%\plaud-meetings-digest)
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

# ---- OS guard: refuse to run on non-Windows -------------------------------
# PowerShell Core (pwsh) runs on Mac/Linux too. If someone pasted this on Mac,
# redirect them to the Mac one-liner so the install path is correct.
$onWindows = ($env:OS -eq 'Windows_NT') -or ($PSVersionTable.Platform -eq 'Win32NT') -or (-not $PSVersionTable.PSEdition)
if (-not $onWindows) {
    Write-Host ""
    Write-Host "✗ This is the Windows bootstrap, but you're on $($PSVersionTable.OS -or [System.Environment]::OSVersion.Platform)." -ForegroundColor Red
    Write-Host ""
    Write-Host "Run this Mac one-liner instead (paste into Terminal, not PowerShell):" -ForegroundColor Yellow
    Write-Host ""
    Write-Host '  bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)' -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

$Repo    = if ($env:PLAUD_DIGEST_REPO)    { $env:PLAUD_DIGEST_REPO }    else { 'GallantSolutions/plaud-meetings-digest' }
$Version = if ($env:PLAUD_DIGEST_VERSION) { $env:PLAUD_DIGEST_VERSION } else { 'latest' }
$Prefix  = if ($env:PLAUD_DIGEST_PREFIX)  { $env:PLAUD_DIGEST_PREFIX }  else { (Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest') }

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Plaud Meetings Digest — Bootstrap (Windows)" -ForegroundColor Cyan
Write-Host "  Repo: $Repo" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Resolve version
if ($Version -eq 'latest') {
    Write-Host "→ Resolving latest release..." -ForegroundColor Blue
    try {
        $rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -UseBasicParsing
        $Version = $rel.tag_name
        Write-Host "✓ Latest release: $Version" -ForegroundColor Green
    } catch {
        Write-Host "⚠ No tagged release found; using main branch." -ForegroundColor Yellow
        $Version = 'main'
    }
}

# Build download URL
if ($Version -eq 'main') {
    $ZipUrl = "https://github.com/$Repo/archive/refs/heads/main.zip"
} else {
    $ZipUrl = "https://github.com/$Repo/archive/refs/tags/$Version.zip"
}

$TmpZip = Join-Path $env:TEMP "plaud-digest-$([System.IO.Path]::GetRandomFileName()).zip"
$TmpDir = Join-Path $env:TEMP "plaud-digest-extract-$([System.IO.Path]::GetRandomFileName())"

Write-Host "→ Downloading $ZipUrl" -ForegroundColor Blue
try {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $TmpZip -UseBasicParsing
} catch {
    Write-Host "✗ Download failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Repo:    https://github.com/$Repo" -ForegroundColor Red
    Write-Host "  Version: $Version" -ForegroundColor Red
    exit 1
}
$ZipSize = [Math]::Round((Get-Item $TmpZip).Length / 1KB, 1)
Write-Host "✓ Downloaded $ZipSize KB" -ForegroundColor Green

Write-Host "→ Extracting..." -ForegroundColor Blue
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
Expand-Archive -Path $TmpZip -DestinationPath $TmpDir -Force

# GitHub renames the extracted folder to <repo>-<branch-or-tag-stripped>
$Extracted = Get-ChildItem -Path $TmpDir -Directory | Where-Object { $_.Name -like 'plaud-meetings-digest*' } | Select-Object -First 1
if (-not $Extracted) {
    Write-Host "✗ Could not find extracted folder" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Extracted to $($Extracted.Name)" -ForegroundColor Green

# Install to canonical location
Write-Host "→ Installing to $Prefix" -ForegroundColor Blue
if (Test-Path $Prefix) {
    Write-Host "⚠ Existing install found — replacing." -ForegroundColor Yellow
    Remove-Item -Path $Prefix -Recurse -Force
}
$ParentDir = Split-Path $Prefix -Parent
if (-not (Test-Path $ParentDir)) { New-Item -ItemType Directory -Path $ParentDir -Force | Out-Null }
Move-Item -Path $Extracted.FullName -Destination $Prefix

Write-Host "✓ Bundle landed at $Prefix" -ForegroundColor Green
Write-Host ""

# Cleanup tmp
try { Remove-Item -Path $TmpZip -Force -ErrorAction SilentlyContinue } catch {}
try { Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue } catch {}

# Chain into install.ps1
Write-Host "→ Launching install.ps1 (will walk through prereqs, OAuth, OneDrive, routing, schedule)" -ForegroundColor Blue
Write-Host ""
$InstallScript = Join-Path $Prefix 'install.ps1'
if (-not (Test-Path $InstallScript)) {
    Write-Host "✗ install.ps1 not found at $InstallScript" -ForegroundColor Red
    exit 1
}

# PowerShell execution policy: this session was started via `iex` from a stream,
# so it inherits the user's session policy. If they're locked down, surface that.
Set-Location $Prefix
& powershell -ExecutionPolicy Bypass -File $InstallScript
