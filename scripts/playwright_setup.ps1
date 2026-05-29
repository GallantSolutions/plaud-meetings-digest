# ============================================================================
# playwright_setup.ps1 — one-time Playwright auth + persistent profile setup
# ============================================================================
# Run once per client install BEFORE flipping config.plaud.method to "auto"
# or "playwright_only". Installs Playwright + Chromium, launches a headed
# browser, lets the operator log into Plaud, saves the session to the
# persistent profile at %LOCALAPPDATA%\plaud-meetings-digest\.playwright-profile\.
#
# Usage:
#   .\scripts\playwright_setup.ps1              # full install + interactive login
#   .\scripts\playwright_setup.ps1 -ReAuth      # session expired; re-login only
#   .\scripts\playwright_setup.ps1 -CodegenMode # launch codegen for selector dev
#   .\scripts\playwright_setup.ps1 -Verify      # check session is alive, no UI
#
# Exit codes:
#   0  — setup complete (or verify passed)
#   1  — Python not available
#   2  — Playwright install failed
#   3  — Chromium download failed
#   4  — Interactive login did not complete (operator cancelled)
#   5  — Verify mode: session expired
# ============================================================================

#Requires -Version 5.1

param(
    [switch]$ReAuth,
    [switch]$CodegenMode,
    [switch]$Verify,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

function Write-Ok   { param([string]$Text) if (-not $Quiet) { Write-Host "✓ $Text" -ForegroundColor Green } }
function Write-Warn { param([string]$Text) Write-Host "⚠ $Text" -ForegroundColor Yellow }
function Write-Err  { param([string]$Text) Write-Host "✗ $Text" -ForegroundColor Red }
function Write-Info { param([string]$Text) if (-not $Quiet) { Write-Host "→ $Text" -ForegroundColor Cyan } }

# ---- Paths ---------------------------------------------------------------
$BundlePrefix = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest'
$ProfileDir   = Join-Path $BundlePrefix '.playwright-profile'
$StagingDir   = Join-Path $BundlePrefix '.playwright-staging'
$ReadyMarker  = Join-Path $BundlePrefix '.playwright-ready'
$BundleScripts = Join-Path $BundlePrefix 'scripts'
$ClientModule  = Join-Path $BundleScripts 'plaud_playwright.py'

New-Item -ItemType Directory -Path $BundlePrefix -Force | Out-Null
New-Item -ItemType Directory -Path $ProfileDir   -Force | Out-Null
New-Item -ItemType Directory -Path $StagingDir   -Force | Out-Null

# ---- Python detection ----------------------------------------------------
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command py -ErrorAction SilentlyContinue).Source
}
if (-not $PythonExe) {
    Write-Err "Python not on PATH. Run install.ps1 (which installs Python) first."
    exit 1
}
Write-Info "Python: $PythonExe"

# ---- Install playwright + chromium --------------------------------------
if (-not $Verify) {
    Write-Info "Installing playwright pip package..."
    try {
        & $PythonExe -m pip install --quiet --upgrade playwright
        if ($LASTEXITCODE -ne 0) { throw "pip install playwright exited $LASTEXITCODE" }
        Write-Ok "playwright installed"
    } catch {
        Write-Err "playwright pip install failed: $($_.Exception.Message)"
        exit 2
    }

    Write-Info "Downloading Chromium (one-time, ~150MB)..."
    try {
        & $PythonExe -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "playwright install chromium exited $LASTEXITCODE" }
        Write-Ok "Chromium installed"
    } catch {
        Write-Err "Chromium download failed (likely proxy/firewall on enterprise machine): $($_.Exception.Message)"
        Write-Warn "Operator: enterprise proxies sometimes block Playwright's CDN. See https://playwright.dev/python/docs/browsers#install-behind-a-firewall"
        exit 3
    }
}

# ---- Codegen mode --------------------------------------------------------
if ($CodegenMode) {
    Write-Info "Launching Playwright Codegen against web.plaud.ai..."
    Write-Warn "Use this only for selector development on the dev machine, not on the client."
    & $PythonExe -m playwright codegen --target=python-async --output="$PSScriptRoot\codegen_out.py" https://web.plaud.ai/
    if (Test-Path "$PSScriptRoot\codegen_out.py") {
        Write-Ok "Codegen output saved → $PSScriptRoot\codegen_out.py"
        Write-Info "Inspect the file. Extract real selectors and paste into config.plaud.playwright.selectors."
    }
    exit 0
}

# ---- Verify-only mode ----------------------------------------------------
if ($Verify) {
    if (-not (Test-Path $ClientModule)) {
        Write-Err "plaud_playwright.py not found at $ClientModule. Re-run install.ps1."
        exit 1
    }
    Write-Info "Probing Plaud session (headless)..."
    & $PythonExe $ClientModule --check-session
    $rc = $LASTEXITCODE
    if ($rc -eq 0) {
        Write-Ok "Session is alive"
        exit 0
    } else {
        Write-Warn "Session expired or never set up. Run this script without -Verify to (re-)authenticate."
        exit 5
    }
}

# ---- Interactive login ---------------------------------------------------
# Use a tiny Python script to spawn a HEADED persistent-context browser at
# web.plaud.ai. Operator logs in. When they close the browser, the session
# cookies remain in the profile dir.
$LoginScript = @"
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE = r'$ProfileDir'

async def main():
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            headless=False,
            viewport={'width': 1280, 'height': 800},
            accept_downloads=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto('https://web.plaud.ai/')
        print('-' * 60, flush=True)
        if r'$ReAuth' == 'True':
            print('Re-auth mode. Sign in to Plaud again, then close the browser window.', flush=True)
        else:
            print('First-run auth. Sign in to Plaud, navigate to your files list, then close the browser window.', flush=True)
        print('Cookies and session state will be saved to the persistent profile.', flush=True)
        print('-' * 60, flush=True)
        # Wait until the operator closes the context.
        closed_event = asyncio.Event()
        ctx.on('close', lambda: closed_event.set())
        await closed_event.wait()

asyncio.run(main())
"@

$LoginScriptPath = Join-Path $env:TEMP "plaud_playwright_login_$([guid]::NewGuid().ToString('N')).py"
$LoginScript | Set-Content -Path $LoginScriptPath -Encoding UTF8

try {
    Write-Info "Launching Plaud login window (headed browser)..."
    & $PythonExe $LoginScriptPath
    $loginRc = $LASTEXITCODE
} finally {
    Remove-Item -Path $LoginScriptPath -ErrorAction SilentlyContinue
}

if ($loginRc -ne 0) {
    Write-Err "Login flow did not complete cleanly (exit $loginRc). Run again to retry."
    exit 4
}

# ---- Verify the session works ------------------------------------------
if (Test-Path $ClientModule) {
    Write-Info "Verifying saved session works (headless probe)..."
    & $PythonExe $ClientModule --check-session
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Headless probe did not find logged-in state. Selectors may need verification."
        Write-Warn "Run: .\scripts\playwright_setup.ps1 -CodegenMode (on dev machine) to confirm selectors."
        # Don't hard-fail — session may still work for actual exports; selector probe is conservative.
    } else {
        Write-Ok "Session verified — Playwright path is ready."
    }
} else {
    Write-Warn "plaud_playwright.py not yet at $ClientModule (install.ps1 likely hasn't placed it). Setup will retry on first auto-update."
}

# ---- Stamp ready marker --------------------------------------------------
$marker = @{
    setup_at = (Get-Date).ToString('o')
    profile_dir = $ProfileDir
    re_auth = [bool]$ReAuth
}
$marker | ConvertTo-Json | Set-Content -Path $ReadyMarker -Encoding UTF8
Write-Ok "Playwright setup complete. Profile at: $ProfileDir"
Write-Info "Next: in config.json, set plaud.method = 'auto' to enable Playwright-primary fetch."
exit 0
