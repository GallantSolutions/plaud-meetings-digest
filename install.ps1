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
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# v2.4.2: Bundle must live at %LOCALAPPDATA%\plaud-meetings-digest so scheduled-task
# targets, version.txt, and auto-update.ps1 paths stay stable across reboots
# (Windows can clear %TEMP%, redirected enterprise Downloads folders, etc.). If
# install.ps1 is running from anywhere else, copy the bundle to canonical first
# and rebase $ScriptDir so every downstream path derives off the stable location.
$CanonicalBundlePrefix = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest'
if ($ScriptDir -ne $CanonicalBundlePrefix) {
    Write-Host "→ Copying bundle to canonical location: $CanonicalBundlePrefix" -ForegroundColor Blue
    $existingLogs = Join-Path $CanonicalBundlePrefix 'logs'
    $logsBackup = Join-Path $env:TEMP "plaud-logs-backup-$([Guid]::NewGuid())"
    if (Test-Path $existingLogs) {
        Move-Item $existingLogs $logsBackup -Force
    }
    if (Test-Path $CanonicalBundlePrefix) {
        Remove-Item $CanonicalBundlePrefix -Recurse -Force
    }
    Copy-Item -Path $ScriptDir -Destination $CanonicalBundlePrefix -Recurse -Force
    if (Test-Path $logsBackup) {
        Move-Item $logsBackup (Join-Path $CanonicalBundlePrefix 'logs') -Force
    }
    $ScriptDir = $CanonicalBundlePrefix
    Write-Host "✓ Bundle at canonical location. Continuing install from there." -ForegroundColor Green
}

$SkillMeetingsSrc   = Join-Path $ScriptDir 'skills\meetings-digest'
$SkillRollupSrc     = Join-Path $ScriptDir 'skills\weekly-rollup'
$ScriptsSrc         = Join-Path $ScriptDir 'scripts'
$ConfigSrc          = Join-Path $ScriptDir 'config\digest-config.template.json'

$SkillMeetingsInstall = Join-Path $HOME '.claude\skills\meetings-digest'
$SkillRollupInstall   = Join-Path $HOME '.claude\skills\weekly-rollup'
$ScriptsInstall       = Join-Path $SkillMeetingsInstall 'scripts'
$ConfigInstall        = Join-Path $SkillMeetingsInstall 'config.json'
$StateDir             = Join-Path $SkillMeetingsInstall 'state'

Write-Header "Plaud Meetings Digest — Windows Installer (v2.4.2)"

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

# ---- Helpers: refresh PATH + vendor-direct fallback ----------------------
# v2.4.1: winget alone isn't reliable on enterprise machines (TLS-MITM proxies,
# AppLocker policies, stale mirror indices). Each prereq tries winget first,
# then falls back to the vendor's official always-latest URL when winget fails.
function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

function Install-FromUrl {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$Filename,
        [Parameter(Mandatory=$true)][string[]]$SilentArgs
    )
    $tmp = Join-Path $env:TEMP $Filename
    try {
        Write-Step "Downloading $Url"
        Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing -TimeoutSec 300
        Write-Step "Running installer with: $($SilentArgs -join ' ')"
        $proc = Start-Process -FilePath $tmp -ArgumentList $SilentArgs -Wait -PassThru -NoNewWindow
        return ($proc.ExitCode -eq 0)
    } finally {
        # Always clean up the temp installer, even on download failure
        Remove-Item -Path $tmp -Force -ErrorAction SilentlyContinue
    }
}

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
    winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
    Refresh-Path
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Warn "winget Node install didn't take. Falling back to direct download from nodejs.org."
        # nodejs.org's "latest LTS" URL pattern. The v20.x major rolls forward
        # to whatever LTS patch is current — always fresh, no mirror lag.
        $arch = if ([System.Environment]::Is64BitOperatingSystem) { 'x64' } else { 'x86' }
        # Resolve the actual filename from the latest-v20.x index page
        try {
            $idx = Invoke-WebRequest -Uri "https://nodejs.org/dist/latest-v20.x/" -UseBasicParsing -TimeoutSec 60
            $msi = ($idx.Content -split "`n" | Select-String -Pattern "node-v[\d\.]+-$arch\.msi" | Select-Object -First 1).Matches.Value
            if ($msi) {
                $url = "https://nodejs.org/dist/latest-v20.x/$msi"
                if (Install-FromUrl -Url $url -Filename "node-lts.msi" -SilentArgs @('/i', "$env:TEMP\node-lts.msi", '/qn', '/norestart')) {
                    Refresh-Path
                }
            }
        } catch {
            Write-Warn "Direct Node download failed: $($_.Exception.Message)"
        }
    }
    if (Get-Command node -ErrorAction SilentlyContinue) {
        Write-Ok "Node $(node -v) installed"
    } else {
        Write-Err "Node install did not complete. Install manually from https://nodejs.org/en/download/ and re-run install.ps1."
        exit 1
    }
}

# Python 3.10+ (v2.4.1: use Python.Python.3 alias which rolls forward to
# latest 3.x major, instead of the pinned 3.11 we had in v2.4.0).
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
    Write-Step "Installing latest Python 3.x via winget..."
    winget install --id Python.Python.3 -e --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
    Refresh-Path
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Warn "winget Python install didn't take. Falling back to direct download from python.org."
        # Resolve the current latest stable 3.x via python.org's JSON API.
        # Parse-by-name (not by API's `version` field, which is just the major
        # int and ties across all 3.x). [version] cast on the trimmed name lets
        # Sort-Object do correct semantic version ordering.
        try {
            $releases = Invoke-RestMethod -Uri "https://www.python.org/api/v2/downloads/release/?is_published=true&pre_release=false&format=json" -UseBasicParsing -TimeoutSec 60
            $candidates = @()
            foreach ($r in $releases) {
                if ($r.name -match '^Python 3\.(\d+)\.(\d+)$' -and [int]$Matches[1] -ge 10) {
                    $candidates += [PSCustomObject]@{
                        Release = $r
                        Semver  = [version]($r.name -replace '^Python ','')
                    }
                }
            }
            $latest = $candidates | Sort-Object -Property Semver -Descending | Select-Object -First 1
            if ($latest) {
                $relId = $latest.Release.resource_uri -replace '.+/(\d+)/$','$1'
                $files = Invoke-RestMethod -Uri "https://www.python.org/api/v2/downloads/release_file/?release=$relId&format=json" -UseBasicParsing -TimeoutSec 60
                $arch = if ([System.Environment]::Is64BitOperatingSystem) { 'amd64' } else { 'win32' }
                $msi = $files | Where-Object { $_.url -match "${arch}\.exe$" } | Select-Object -First 1
                if ($msi) {
                    Write-Step "Installing $($latest.Release.name) from python.org"
                    if (Install-FromUrl -Url $msi.url -Filename "python-stable.exe" -SilentArgs @('/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test=0', 'Include_doc=0')) {
                        Refresh-Path
                    }
                }
            }
        } catch {
            Write-Warn "Direct Python download failed: $($_.Exception.Message)"
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Ok "Python $(python --version) installed"
    } else {
        Write-Err "Python install did not complete. Install manually from https://www.python.org/downloads/windows/ and re-run install.ps1."
        exit 1
    }
}

# Git for Windows — required by auto-update.ps1's GitHub pull path and by
# Claude Code's bash invocation on Windows. Was missing from v2.4.0; the
# Kingsway/Ben install hit this gap manually.
$gitOk = $false
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Ok "Git: $(git --version)"
    $gitOk = $true
}
if (-not $gitOk) {
    Write-Step "Installing Git for Windows via winget..."
    winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
    Refresh-Path
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Warn "winget Git install didn't take. Falling back to direct download from git-for-windows."
        try {
            $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/git-for-windows/git/releases/latest" -UseBasicParsing -TimeoutSec 60
            $arch = if ([System.Environment]::Is64BitOperatingSystem) { '64-bit' } else { '32-bit' }
            $asset = $rel.assets | Where-Object { $_.name -match "Git-.*-${arch}\.exe$" -and $_.name -notmatch 'portable' } | Select-Object -First 1
            if ($asset) {
                if (Install-FromUrl -Url $asset.browser_download_url -Filename "git-installer.exe" -SilentArgs @('/VERYSILENT', '/NORESTART', '/NOCANCEL', '/SP-', '/SUPPRESSMSGBOXES', '/COMPONENTS=icons,ext\reg\shellhere,assoc,assoc_sh')) {
                    Refresh-Path
                }
            }
        } catch {
            Write-Warn "Direct Git download failed: $($_.Exception.Message)"
        }
    }
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Ok "Git $(git --version) installed"
        # Set CLAUDE_CODE_GIT_BASH_PATH so Claude Code finds bash.exe
        $gitDir = Split-Path -Parent (Get-Command git).Source
        $bashPath = Join-Path (Split-Path -Parent $gitDir) 'bin\bash.exe'
        if (Test-Path $bashPath) {
            [Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", $bashPath, "User")
            Write-Ok "CLAUDE_CODE_GIT_BASH_PATH set to $bashPath"
        }
    } else {
        Write-Warn "Git install did not complete. Some features (auto-update from GitHub, Claude Code bash invocation) may not work. Install manually from https://git-scm.com/download/win."
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
    # Claude Code's installer (Anthropic's claude.ai/install.ps1) drops the binary
    # into user-local locations that aren't always added to the registry PATH that
    # the current session inherits from. Probe known install locations and prepend
    # to $env:Path so the rest of install.ps1 can invoke `claude` in the same
    # session without a shell restart.
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        $knownClaudePaths = @(
            "$env:LOCALAPPDATA\AnthropicClaude\bin",
            "$env:LOCALAPPDATA\Programs\claude-code",
            "$env:LOCALAPPDATA\Programs\Claude",
            "$env:USERPROFILE\.claude\bin",
            "$env:USERPROFILE\.local\bin",
            "$env:APPDATA\npm"
        )
        foreach ($candidate in $knownClaudePaths) {
            if (Test-Path "$candidate\claude.exe") {
                $env:Path = "$candidate;$env:Path"
                Write-Host "  (resolved claude.exe via $candidate)"
                break
            }
        }
    }
    # Last-resort: recursive search of $env:LOCALAPPDATA for claude.exe (slow but
    # exhaustive — fires only when the known-path probe missed).
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        $found = Get-ChildItem -Path $env:LOCALAPPDATA -Recurse -Filter 'claude.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $env:Path = "$($found.Directory.FullName);$env:Path"
            Write-Host "  (resolved claude.exe via recursive search: $($found.Directory.FullName))"
        }
    }
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
# Defensive: Read-Host can return $null when stdin is closed (e.g. CI environments
# or sandboxed installs). Fall back to %USERPROFILE%\OneDrive so the install can
# proceed; operator can still override via the auto-detect path or by editing
# config.json post-install.
if (-not $onedrive) {
    $onedrive = Join-Path $env:USERPROFILE 'OneDrive'
    Write-Warn "No OneDrive path supplied — defaulting to $onedrive"
}
$onedrive = $onedrive.Trim()
if (-not (Test-Path $onedrive)) {
    Write-Warn "Path '$onedrive' does not exist."
    $createIt = Read-Host "Create it? [Y/n]"
    # Defensive: null (closed stdin) is treated the same as "Y" (the default).
    if (-not $createIt -or $createIt -ne 'n') { New-Item -ItemType Directory -Path $onedrive -Force | Out-Null }
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
Write-Host "  • Kingsway Pharma   → folder 'Kingsway Pharma'   → 'KPM' (meetings) + 'KPR' (rollup)  → per-week subfolders → INCLUDED in Friday rollup"
Write-Host "  • Committee         → folder 'Committee'         → 'CMM' (meetings) + 'CMR' (rollup)  → per-week subfolders → INCLUDED in Friday rollup"
Write-Host "  • Church            → folder 'Church'            → 'CHM' (meetings) + 'CHR' (rollup)  → per-week subfolders → INCLUDED in Friday rollup"
Write-Host "  • Personal          → folder 'Personal'          → 'PM'  (meetings) + 'PR'  (rollup)  → per-week subfolders → INCLUDED in Friday rollup"
Write-Host ""
Write-Host "  Files land as: {prefix}.{short topic} ({attendees}).docx"
Write-Host "    e.g. Kingsway Pharma\KPM.May 25-29, 2026 (Week 22)\KPM.Q3 Plans (John Smith).docx"
Write-Host "    rollup: Kingsway Pharma\KPM.May 25-29, 2026 (Week 22)\KPR.May 25-29, 2026 (Week 22).docx"
Write-Host ""
$customize = Read-Host "Use these defaults? [Y/n]"
$routing = @()
if ($customize -eq 'n') {
    Write-Host "Enter meeting types, one per line. For each (pipe-separated, 6 fields):"
    Write-Host "  keyword|folder|filename_prefix|rollup_filename_prefix_or_none|weekly_subfolders(yes/no)|include_in_rollup(yes/no)"
    Write-Host "Example: Kingsway Pharma|Kingsway Pharma|KPM|KPR|yes|yes"
    Write-Host "Example: Personal|Personal|PM|none|no|no"
    Write-Host "Blank line to finish."
    while ($true) {
        $line = Read-Host "Meeting type"
        if (-not $line) { break }
        $parts = $line.Split('|')
        if ($parts.Length -ne 6) { Write-Warn "Need 6 pipe-separated fields — try again"; continue }
        $rollupPrefix = $parts[3].Trim()
        if ($rollupPrefix -eq 'none' -or $rollupPrefix -eq '') { $rollupPrefix = $null }
        $routing += @{
            keyword                   = $parts[0].Trim()
            folder                    = $parts[1].Trim()
            filename_prefix           = $parts[2].Trim()
            rollup_filename_prefix    = $rollupPrefix
            weekly_subfolders         = ($parts[4].Trim().ToLower() -eq 'yes')
            include_in_weekly_rollup  = ($parts[5].Trim().ToLower() -eq 'yes')
        }
    }
} else {
    $routing = @(
        @{ keyword = "Kingsway Pharma"; folder = "Kingsway Pharma"; filename_prefix = "KPM"; rollup_filename_prefix = "KPR"; weekly_subfolders = $true; include_in_weekly_rollup = $true },
        @{ keyword = "Committee";       folder = "Committee";       filename_prefix = "CMM"; rollup_filename_prefix = "CMR"; weekly_subfolders = $true; include_in_weekly_rollup = $true },
        @{ keyword = "Church";          folder = "Church";          filename_prefix = "CHM"; rollup_filename_prefix = "CHR"; weekly_subfolders = $true; include_in_weekly_rollup = $true },
        @{ keyword = "Personal";        folder = "Personal";        filename_prefix = "PM";  rollup_filename_prefix = "PR";  weekly_subfolders = $true; include_in_weekly_rollup = $true }
    )
}
Write-Ok "Configured $($routing.Length) meeting type(s)"

# ============================================================================
# Step 4b — Heartbeat (Gallant operator telemetry)
# ============================================================================
Write-Header "Step 4b — Heartbeat (operator alerts when something breaks)"
Write-Host "Gallant uses Healthchecks.io to alert the operator if a scheduled run"
Write-Host "doesn't complete on time (machine asleep, Claude died, task de-registered,"
Write-Host "network down). Setup runbook: scripts\..\OPERATOR-INSTALL-GUIDE.md."
Write-Host ""
Write-Host "Operator: provide one Healthchecks ping UUID per scheduled job, or paste"
Write-Host "a base path + four UUIDs. Press Enter on any prompt to skip that check."
Write-Host ""

$heartbeatEnabled = $false
$heartbeatBase = 'https://hc-ping.com'
$checkLunch = $null
$checkEod = $null
$checkRollup = $null
$checkAutoUpdate = $null

# Env-var path (non-interactive sandboxed installs + cleaner operator flow)
if ($env:GALLANT_HEARTBEAT_BASE) { $heartbeatBase = $env:GALLANT_HEARTBEAT_BASE }
if ($env:GALLANT_HEARTBEAT_CHECK_LUNCH)       { $checkLunch       = $env:GALLANT_HEARTBEAT_CHECK_LUNCH }
if ($env:GALLANT_HEARTBEAT_CHECK_EOD)         { $checkEod         = $env:GALLANT_HEARTBEAT_CHECK_EOD }
if ($env:GALLANT_HEARTBEAT_CHECK_ROLLUP)      { $checkRollup      = $env:GALLANT_HEARTBEAT_CHECK_ROLLUP }
if ($env:GALLANT_HEARTBEAT_CHECK_AUTO_UPDATE) { $checkAutoUpdate  = $env:GALLANT_HEARTBEAT_CHECK_AUTO_UPDATE }

$envProvided = $checkLunch -or $checkEod -or $checkRollup -or $checkAutoUpdate
if (-not $envProvided) {
    $enable = Read-Host "Enable heartbeat? [Y/n]"
    if (-not $enable -or $enable -ne 'n') {
        $baseInput = Read-Host "Ping base URL [default https://hc-ping.com]"
        if ($baseInput) { $heartbeatBase = $baseInput.Trim() }
        $checkLunch      = Read-Host "Check UUID for daily 11:00 AM (lunch)"
        $checkEod        = Read-Host "Check UUID for daily 4:00 PM (eod)"
        $checkRollup     = Read-Host "Check UUID for Friday 4:30 PM (rollup)"
        $checkAutoUpdate = Read-Host "Check UUID for daily 3:00 AM (auto-update)"
    }
}
# Normalize empty strings to $null
foreach ($v in 'checkLunch','checkEod','checkRollup','checkAutoUpdate') {
    if (-not (Get-Variable $v -ValueOnly)) { Set-Variable $v -Value $null }
    else { Set-Variable $v -Value (Get-Variable $v -ValueOnly).Trim() }
}
if ($checkLunch -or $checkEod -or $checkRollup -or $checkAutoUpdate) {
    $heartbeatEnabled = $true
    Write-Ok "Heartbeat enabled"
} else {
    Write-Warn "Heartbeat skipped — operator gets no alerts when jobs fail silently"
}

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

# Tray subpackage — required because tray_bridge.py imports `from tray import state`.
# Recursively copy scripts/tray/, excluding dev artifacts (preview HTML, cache, the
# tray installer itself, and the README) so client install stays clean.
$TrayPkgSrc  = Join-Path $ScriptsSrc 'tray'
$TrayPkgDest = Join-Path $ScriptsInstall 'tray'
if (Test-Path $TrayPkgDest) { Remove-Item -Recurse -Force $TrayPkgDest }
$trayExclude = @('preview.html', 'README.md', 'install_tray.ps1', '__pycache__')
Copy-Item -Recurse -Force -Path $TrayPkgSrc -Destination $TrayPkgDest -Exclude $trayExclude
# -Exclude on Copy-Item only filters the top-level — sweep nested __pycache__ too.
Get-ChildItem -Path $TrayPkgDest -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Ok "Tray subpackage installed at $TrayPkgDest"

# Build config.json
$configTemplate = Get-Content $ConfigSrc -Raw | ConvertFrom-Json
$configTemplate.installed_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$configTemplate.platform = 'windows'
$configTemplate.destination.type = 'word_onedrive'
$configTemplate.destination.onedrive_folder = $onedrive
$configTemplate.meeting_routing.types = $routing

# Heartbeat block (operator-supplied)
$configTemplate.gallant_heartbeat.enabled = $heartbeatEnabled
$configTemplate.gallant_heartbeat.ping_base_url = $heartbeatBase
$configTemplate.gallant_heartbeat.checks.lunch = $checkLunch
$configTemplate.gallant_heartbeat.checks.eod = $checkEod
$configTemplate.gallant_heartbeat.checks.rollup = $checkRollup
$configTemplate.gallant_heartbeat.checks.auto_update = $checkAutoUpdate

$configJson = $configTemplate | ConvertTo-Json -Depth 10
Set-Content -Path $ConfigInstall -Value $configJson -Encoding UTF8

Write-Ok "Skills installed at $SkillMeetingsInstall and $SkillRollupInstall"
Write-Ok "Config written to $ConfigInstall"

# ---- Write version stamp (for auto-update version comparison) ------------
# Bundle prefix is wherever bootstrap landed us — derive from $ScriptDir.
$BundlePrefix = $ScriptDir
$VersionFile = Join-Path $BundlePrefix 'version.txt'
# Read version from package.json equivalent — use the config version as the
# canonical version stamp (single source of truth for the bundle's identity).
$bundleVersion = $configTemplate.version
Set-Content -Path $VersionFile -Value $bundleVersion -Encoding UTF8
Write-Ok "Bundle version stamped: $bundleVersion -> $VersionFile"

# ============================================================================
# Step 5c — Tray widget (Kingsway action items in the system tray)
# ============================================================================
Write-Header "Step 5c — Installing tray widget"

# install_tray.ps1 installs the pywebview/pystray/Pillow/watchdog deps, copies the
# tray subpackage to %LOCALAPPDATA%/plaud-tray, and creates a Startup shortcut.
# Failure here is non-fatal — the rollup pipeline still works without the tray;
# the operator just doesn't get the system-tray UI.
$TrayInstaller = Join-Path $ScriptsSrc 'tray\install_tray.ps1'
if (Test-Path $TrayInstaller) {
    try {
        & $TrayInstaller -Quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Tray widget installed"
        } else {
            Write-Warn "Tray widget install returned non-zero exit code $LASTEXITCODE. Re-run scripts\tray\install_tray.ps1 manually to retry."
        }
    } catch {
        Write-Warn "Tray widget install raised: $($_.Exception.Message). Re-run scripts\tray\install_tray.ps1 manually."
    }
} else {
    Write-Warn "Tray installer not found at $TrayInstaller — skipping tray install."
}

# ============================================================================
# Step 6 — Schedule three jobs
# ============================================================================
Write-Header "Step 6/6 — Schedule three jobs"

Write-Host "This will install three Windows Task Scheduler jobs:"
Write-Host "  • Daily 11:00 AM — lunch meetings pull"
Write-Host "  • Daily  4:00 PM — afternoon meetings pull"
Write-Host "  • Friday 4:30 PM — weekly rollup (Kingsway Pharma + Committee)"
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
Write-Host "  • Scheduled:   Runs at 11:00 AM and 4:00 PM daily; Friday 4:30 PM rollup"
Write-Host "  • Output:      $plaudFolder"
Write-Host "  • Logs:        $HOME\AppData\Local\plaud-meetings-digest\logs\"
Write-Host ""
Write-Host "Train the client: tell them to ALWAYS state the meeting type at the start of every Plaud recording" -ForegroundColor Yellow
Write-Host "(e.g., 'Kingsway Pharma meeting with John Smith'). Without this, recordings route to 'Uncategorized'." -ForegroundColor Yellow
Write-Host ""
Write-Host "To remove later: cd to this folder and run .\uninstall.ps1"
