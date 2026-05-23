# ============================================================================
# Plaud Meetings Digest — Windows All-in-One Installer
# ============================================================================
#
# Single-command install that:
#   1. Checks/installs prereqs (Node 20+, Python 3.11+, Claude Code CLI) via winget
#   2. Installs python-docx for Word output
#   3. Installs Plaud MCP server (one-time OAuth in browser)
#   4. Copies the meetings-digest + weekly-rollup skills into Claude Code
#   5. Configures OneDrive output destination + meeting routing keywords
#   6. Installs the three Windows Task Scheduler jobs (lunch / EOD / Friday rollup)
#
# Run as the recipient user (NOT elevated unless winget asks for it).
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

# ---- OS guard --------------------------------------------------------------
$onWindows = ($env:OS -eq 'Windows_NT') -or ($PSVersionTable.Platform -eq 'Win32NT') -or (-not $PSVersionTable.PSEdition)
if (-not $onWindows) {
    Write-Host ""
    Write-Host "✗ install.ps1 is Windows-only. You appear to be on a different OS." -ForegroundColor Red
    Write-Host "  On Mac, run: bash ./install.sh" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# ---- Colors --------------------------------------------------------------
function Write-Header { param([string]$Text)
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
}
function Write-Step { param([string]$Text) Write-Host "→ $Text" -ForegroundColor Blue }
function Write-Ok   { param([string]$Text) Write-Host "✓ $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text) Write-Host "⚠ $Text" -ForegroundColor Yellow }
function Write-Err  { param([string]$Text) Write-Host "✗ $Text" -ForegroundColor Red }

# ---- Resolve paths --------------------------------------------------------
$ScriptDir          = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillMeetingsSrc   = Join-Path $ScriptDir 'skills\meetings-digest'
$SkillRollupSrc     = Join-Path $ScriptDir 'skills\weekly-rollup'
$ScriptsSrc         = Join-Path $ScriptDir 'scripts'
$ConfigSrc          = Join-Path $ScriptDir 'config\digest-config.template.json'

$SkillMeetingsInstall = Join-Path $HOME '.claude\skills\meetings-digest'
$SkillRollupInstall   = Join-Path $HOME '.claude\skills\weekly-rollup'
$ScriptsInstall       = Join-Path $SkillMeetingsInstall 'scripts'
$ConfigInstall        = Join-Path $SkillMeetingsInstall 'config.json'
$StateDir             = Join-Path $SkillMeetingsInstall 'state'

Write-Header "Plaud Meetings Digest — Windows Installer (v2.0.0)"

# ============================================================================
# Step 1 — Prerequisites
# ============================================================================
Write-Step "Step 1/6 — Checking prerequisites"

# winget itself
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Err "winget not found. Install 'App Installer' from the Microsoft Store, then re-run this script."
    exit 1
}
Write-Ok "winget found"

# Node 20+
$nodeOk = $false
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVer = (node -v) -replace 'v',''
    $nodeMajor = [int]($nodeVer.Split('.')[0])
    if ($nodeMajor -ge 20) {
        Write-Ok "Node $nodeVer"
        $nodeOk = $true
    } else {
        Write-Warn "Node $nodeVer found, but v20+ required"
    }
}
if (-not $nodeOk) {
    Write-Step "Installing Node.js 20 LTS via winget..."
    winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements
    # Refresh PATH for current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    if (Get-Command node -ErrorAction SilentlyContinue) {
        Write-Ok "Node $(node -v) installed"
    } else {
        Write-Err "Node install may have succeeded but isn't on PATH yet. Close this terminal, open a fresh PowerShell, and re-run install.ps1."
        exit 1
    }
}

# Python 3.11+
$pythonOk = $false
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = (python --version 2>&1) -replace 'Python ',''
    $pyParts = $pyVer.Split('.')
    if ([int]$pyParts[0] -ge 3 -and [int]$pyParts[1] -ge 10) {
        Write-Ok "Python $pyVer"
        $pythonOk = $true
    }
}
if (-not $pythonOk) {
    Write-Step "Installing Python 3.11 via winget..."
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Ok "Python $(python --version) installed"
    } else {
        Write-Err "Python install may have succeeded but isn't on PATH yet. Close + reopen PowerShell and re-run install.ps1."
        exit 1
    }
}

# Claude Code CLI — preferred: official Anthropic PowerShell installer (auto-updates).
# Fallback: winget Anthropic.ClaudeCode (does not auto-update).
$claudeOk = $false
if (Get-Command claude -ErrorAction SilentlyContinue) {
    Write-Ok "Claude Code: $(claude --version 2>&1 | Select-Object -First 1)"
    $claudeOk = $true
}
if (-not $claudeOk) {
    Write-Step "Installing Claude Code via Anthropic's official PowerShell installer..."
    try {
        $installer = Invoke-RestMethod -Uri 'https://claude.ai/install.ps1' -UseBasicParsing
        Invoke-Expression $installer
    } catch {
        Write-Warn "Official installer failed: $($_.Exception.Message)"
        Write-Step "Falling back to winget (Anthropic.ClaudeCode)..."
        winget install --id Anthropic.ClaudeCode -e --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Both install methods failed. Try the manual installer at https://code.claude.com/docs/en/setup"
            exit 1
        }
    }
    # Refresh PATH for current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    if (Get-Command claude -ErrorAction SilentlyContinue) {
        Write-Ok "Claude Code installed: $(claude --version 2>&1 | Select-Object -First 1)"
    } else {
        Write-Err "Claude Code install may have succeeded but isn't on PATH yet. Close + reopen PowerShell and re-run install.ps1."
        exit 1
    }
}

# python-docx
Write-Step "Installing python-docx (for Word output)..."
$pipQuiet = python -m pip install --user --quiet python-docx 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "python-docx install failed via --user; trying without flag..."
    python -m pip install --quiet python-docx
}
Write-Ok "python-docx ready"

# ============================================================================
# Step 2 — Plaud MCP server
# ============================================================================
Write-Header "Step 2/6 — Installing Plaud MCP server"
Write-Host "This will open a browser for Plaud OAuth."
Write-Host "Sign into your Plaud account and click Authorize." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to continue (or Ctrl+C to abort)"

npx -y "@plaud-ai/mcp@latest" install
if ($LASTEXITCODE -ne 0) {
    Write-Err "Plaud MCP install failed. See output above."
    exit 1
}
Write-Ok "Plaud MCP installed and authorized"

# ============================================================================
# Step 3 — Output destination: OneDrive
# ============================================================================
Write-Header "Step 3/6 — Configuring OneDrive output"

# Try to resolve OneDrive automatically
$onedrive = python "$ScriptsSrc\onedrive_resolve.py" 2>$null
if (-not $onedrive) {
    Write-Warn "Could not auto-detect OneDrive."
    $onedrive = Read-Host "Enter your OneDrive sync folder path (e.g., C:\Users\<you>\OneDrive)"
}
$onedrive = $onedrive.Trim()
if (-not (Test-Path $onedrive)) {
    Write-Warn "Path '$onedrive' does not exist."
    $createIt = Read-Host "Create it? [Y/n]"
    if ($createIt -ne 'n') { New-Item -ItemType Directory -Path $onedrive -Force | Out-Null }
}
Write-Ok "OneDrive folder: $onedrive"
$plaudFolder = Join-Path $onedrive 'Plaud Meetings'
New-Item -ItemType Directory -Path $plaudFolder -Force | Out-Null
Write-Ok "Created '$plaudFolder' for output"

# ============================================================================
# Step 4 — Meeting routing
# ============================================================================
Write-Header "Step 4/6 — Configure meeting routing"

Write-Host "When the client starts each Plaud recording, they should state the meeting type"
Write-Host "(e.g., 'Kingsway Pharma meeting with John Smith' or 'Sunday church reflection')."
Write-Host "The skill matches the spoken opening line to the keywords below to route to the right folder."
Write-Host ""
Write-Host "Default meeting types for this client:"
Write-Host "  • Kingsway Pharma   → folder 'Kingsway Pharma'   → INCLUDED in Friday rollup"
Write-Host "  • Church            → folder 'Church'            → excluded from rollup"
Write-Host "  • Personal          → folder 'Personal'          → excluded from rollup"
Write-Host ""
$customize = Read-Host "Use these defaults? [Y/n]"
$routing = @()
if ($customize -eq 'n') {
    Write-Host "Enter meeting types, one per line. For each: keyword|folder|include_in_rollup (yes/no)."
    Write-Host "Example: Kingsway Pharma|Kingsway Pharma|yes"
    Write-Host "Blank line to finish."
    while ($true) {
        $line = Read-Host "Meeting type"
        if (-not $line) { break }
        $parts = $line.Split('|')
        if ($parts.Length -ne 3) { Write-Warn "Format: keyword|folder|yes-or-no — try again"; continue }
        $routing += @{
            keyword                   = $parts[0].Trim()
            folder                    = $parts[1].Trim()
            include_in_weekly_rollup  = ($parts[2].Trim().ToLower() -eq 'yes')
        }
    }
} else {
    $routing = @(
        @{ keyword = "Kingsway Pharma"; folder = "Kingsway Pharma"; include_in_weekly_rollup = $true  },
        @{ keyword = "Church";          folder = "Church";          include_in_weekly_rollup = $false },
        @{ keyword = "Personal";        folder = "Personal";        include_in_weekly_rollup = $false }
    )
}
Write-Ok "Configured $($routing.Length) meeting type(s)"

# ============================================================================
# Step 5 — Install skills + scripts + config
# ============================================================================
Write-Header "Step 5/6 — Installing skills into Claude Code"

New-Item -ItemType Directory -Path $SkillMeetingsInstall -Force | Out-Null
New-Item -ItemType Directory -Path $SkillRollupInstall   -Force | Out-Null
New-Item -ItemType Directory -Path $ScriptsInstall       -Force | Out-Null
New-Item -ItemType Directory -Path $StateDir             -Force | Out-Null

Copy-Item "$SkillMeetingsSrc\SKILL.md" "$SkillMeetingsInstall\SKILL.md" -Force
Copy-Item "$SkillRollupSrc\SKILL.md"   "$SkillRollupInstall\SKILL.md"   -Force
Copy-Item "$ScriptsSrc\*.py" "$ScriptsInstall" -Force

# Build config.json
$configTemplate = Get-Content $ConfigSrc -Raw | ConvertFrom-Json
$configTemplate.installed_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$configTemplate.platform = 'windows'
$configTemplate.destination.type = 'word_onedrive'
$configTemplate.destination.onedrive_folder = $onedrive
$configTemplate.meeting_routing.types = $routing

$configJson = $configTemplate | ConvertTo-Json -Depth 10
Set-Content -Path $ConfigInstall -Value $configJson -Encoding UTF8

Write-Ok "Skills installed at $SkillMeetingsInstall and $SkillRollupInstall"
Write-Ok "Config written to $ConfigInstall"

# ============================================================================
# Step 6 — Schedule three jobs
# ============================================================================
Write-Header "Step 6/6 — Schedule three jobs"

Write-Host "This will install three Windows Task Scheduler jobs:"
Write-Host "  • Daily 12:30 PM — lunch meetings pull"
Write-Host "  • Daily  5:00 PM — afternoon meetings pull"
Write-Host "  • Friday 5:30 PM — weekly rollup (Kingsway Pharma only)"
Write-Host ""
$schedule = Read-Host "Enable scheduled runs? [Y/n]"
if ($schedule -ne 'n') {
    & "$ScriptsSrc\schedule.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Schedule install failed. You can re-run scripts\schedule.ps1 later."
    }
}

# ============================================================================
# Done
# ============================================================================
Write-Header "✓ Installation complete"
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  • Test now:    claude -p `"/meetings-digest`""
Write-Host "  • Scheduled:   Runs at 12:30 PM and 5:00 PM daily; Friday 5:30 PM rollup"
Write-Host "  • Output:      $plaudFolder"
Write-Host "  • Logs:        $HOME\AppData\Local\plaud-meetings-digest\logs\"
Write-Host ""
Write-Host "Train the client: tell them to ALWAYS state the meeting type at the start of every Plaud recording" -ForegroundColor Yellow
Write-Host "(e.g., 'Kingsway Pharma meeting with John Smith'). Without this, recordings route to 'Uncategorized'." -ForegroundColor Yellow
Write-Host ""
Write-Host "To remove later: cd to this folder and run .\uninstall.ps1"
