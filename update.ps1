# ============================================================================
# update.ps1 — operator-initiated updater (Windows)  [v2.5.0+]
# ============================================================================
# Replaces the deprecated nightly auto-update task (removed in v2.5.0). Run
# this manually when you want to upgrade the bundle to the latest GitHub
# release. Nothing self-updates anymore — updates are deliberate.
#
#   .\update.ps1            # check + apply the latest release if newer
#   .\update.ps1 -Check     # report only: is a newer version available?
#   .\update.ps1 -DryRun    # show what would happen, change nothing
#   .\update.ps1 -Tag 2.5.0 # update to a specific tag
#
# What it does on apply:
#   1. Resolves the target version (latest release, or -Tag)
#   2. Snapshots the current bundle to <prefix>\.versions\<old-tag>\ (manual
#      rollback aid — copy it back if a release misbehaves)
#   3. Downloads + extracts the release zip, replaces bundle files
#      (preserves config.json + dedup state + logs)
#   4. Pushes updated SKILL.md + scripts into the live ~/.claude install
#   5. Re-runs schedule.ps1 to refresh the Scheduled Tasks
#   6. Stamps version.txt (BOM-less)
# ============================================================================

#Requires -Version 5.1

param(
    [Parameter(Mandatory=$false)] [string]$BundlePrefix = '',
    [Parameter(Mandatory=$false)] [string]$ConfigPath = '',
    [Parameter(Mandatory=$false)] [string]$Repo = '',
    [Parameter(Mandatory=$false)] [string]$Tag = '',
    [Parameter(Mandatory=$false)] [switch]$Check,
    [Parameter(Mandatory=$false)] [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

if (-not $BundlePrefix) { $BundlePrefix = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest' }
if (-not $ConfigPath)   { $ConfigPath = Join-Path $HOME '.claude\skills\meetings-digest\config.json' }

$LogDir = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest\logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir 'update.log'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Log {
    param([string]$Message)
    $line = "[$(Get-Date -Format o)] $Message"
    try { Add-Content -Path $LogPath -Value $line -Encoding UTF8 } catch {}
    Write-Host $line
}

Log "=== update.ps1 starting (Check=$Check DryRun=$DryRun) ==="

# ---- Resolve repo (config, then -Repo, then sane default) ----------------
if (-not $Repo -and (Test-Path $ConfigPath)) {
    try {
        $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        if ($config.gallant_auto_update -and $config.gallant_auto_update.repo) {
            $Repo = $config.gallant_auto_update.repo
        }
    } catch { Log "WARN: could not parse config ($($_.Exception.Message)) — falling back to default repo" }
}
if (-not $Repo) { $Repo = 'GallantSolutions/plaud-meetings-digest' }

# ---- Current version -----------------------------------------------------
$VersionFile = Join-Path $BundlePrefix 'version.txt'
$currentVersion = ''
if (Test-Path $VersionFile) { $currentVersion = (Get-Content $VersionFile -Raw).Trim() }
Log "Current version: '$currentVersion'"

# ---- Resolve target version ----------------------------------------------
$targetVersion = ''
if ($Tag) {
    $targetVersion = $Tag
    Log "Target (explicit -Tag): $targetVersion"
} else {
    try {
        $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -UseBasicParsing -TimeoutSec 30
        $targetVersion = $release.tag_name
    } catch {
        Log "ERROR: could not resolve latest release for $Repo : $($_.Exception.Message)"
        exit 1
    }
    Log "Target (latest release): $targetVersion"
}

if ($targetVersion -eq $currentVersion) {
    Write-Host "✓ Already on the latest version ($currentVersion)." -ForegroundColor Green
    Log "Already current — nothing to do"
    exit 0
}

# ---- Check-only mode -----------------------------------------------------
if ($Check) {
    Write-Host "⬆ A newer version is available: $currentVersion -> $targetVersion" -ForegroundColor Yellow
    Write-Host "  Run  .\update.ps1  to upgrade."
    Log "Check: newer version available ($currentVersion -> $targetVersion)"
    exit 10   # distinct non-zero so a caller can detect 'update available'
}

if ($DryRun) {
    Write-Host "DRY RUN: would update $currentVersion -> $targetVersion" -ForegroundColor Cyan
    Log "DRY RUN — no changes made"
    exit 0
}

# ---- Snapshot current bundle (manual rollback aid) -----------------------
if ($currentVersion) {
    $snapshotDir = Join-Path $BundlePrefix ".versions\$currentVersion"
    if (Test-Path $snapshotDir) {
        Log "Snapshot already exists at $snapshotDir — leaving it"
    } else {
        Log "Snapshotting current bundle to $snapshotDir"
        try {
            New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null
            Get-ChildItem -Path $BundlePrefix -Force | Where-Object { $_.Name -notin @('.versions', 'logs') } | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination $snapshotDir -Recurse -Force
            }
        } catch { Log "WARN: snapshot failed ($($_.Exception.Message)) — proceeding anyway" }
    }
}

# ---- Download + extract --------------------------------------------------
$tmpZip = Join-Path $env:TEMP "gallant-update-$([System.IO.Path]::GetRandomFileName()).zip"
$tmpExtract = Join-Path $env:TEMP "gallant-update-extract-$([System.IO.Path]::GetRandomFileName())"
$zipUrl = "https://github.com/$Repo/archive/refs/tags/$targetVersion.zip"
Log "Downloading $zipUrl"
try {
    Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing -TimeoutSec 300
} catch { Log "ERROR: download failed: $($_.Exception.Message)"; exit 1 }

New-Item -ItemType Directory -Path $tmpExtract -Force | Out-Null
try { Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force }
catch { Log "ERROR: extract failed: $($_.Exception.Message)"; exit 1 }

$extracted = Get-ChildItem -Path $tmpExtract -Directory | Select-Object -First 1
if (-not $extracted) { Log "ERROR: extracted folder not found"; exit 1 }

# ---- Replace bundle files (preserve .versions / logs / live config) ------
Log "Replacing bundle files at $BundlePrefix"
try {
    Get-ChildItem -Path $extracted.FullName -Force | ForEach-Object {
        $destPath = Join-Path $BundlePrefix $_.Name
        if (Test-Path $destPath) { Remove-Item -Path $destPath -Recurse -Force }
        Copy-Item -Path $_.FullName -Destination $destPath -Recurse -Force
    }
} catch { Log "ERROR: file replacement failed: $($_.Exception.Message)"; exit 1 }

# ---- Push updated SKILL.md + scripts into the live ~/.claude install -----
$liveSkillsRoot = Join-Path $HOME '.claude\skills'
if (Test-Path (Join-Path $BundlePrefix 'skills')) {
    Get-ChildItem -Path (Join-Path $BundlePrefix 'skills') -Directory | ForEach-Object {
        $liveSkill = Join-Path $liveSkillsRoot $_.Name
        $sourceSkillMd = Join-Path $_.FullName 'SKILL.md'
        if ((Test-Path $liveSkill) -and (Test-Path $sourceSkillMd)) {
            Copy-Item -Path $sourceSkillMd -Destination (Join-Path $liveSkill 'SKILL.md') -Force
            Log "Updated SKILL.md for $($_.Name)"
        }
    }
}
$liveScripts = Join-Path $liveSkillsRoot 'meetings-digest\scripts'
if (Test-Path $liveScripts) {
    $bundleScripts = Join-Path $BundlePrefix 'scripts'
    $scriptExclude = @('preview.html', 'README.md', 'install_tray.ps1', '__pycache__')
    Get-ChildItem -Path $bundleScripts -Filter '*.py' -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $liveScripts -Force
    }
    Get-ChildItem -Path $bundleScripts -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $destSubdir = Join-Path $liveScripts $_.Name
        if (Test-Path $destSubdir) { Remove-Item -Recurse -Force $destSubdir }
        Copy-Item -Recurse -Force -Path $_.FullName -Destination $destSubdir -Exclude $scriptExclude
        Get-ChildItem -Path $destSubdir -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    Log "Updated Python helpers + subpackages in $liveScripts"
}

# ---- Stamp version (BOM-less) --------------------------------------------
[System.IO.File]::WriteAllText($VersionFile, $targetVersion, $Utf8NoBom)
Log "Wrote version.txt = $targetVersion"

# ---- Re-register Scheduled Tasks (task defs may have changed) ------------
$ScheduleScript = Join-Path $BundlePrefix 'scripts\schedule.ps1'
if (Test-Path $ScheduleScript) {
    Log "Re-running schedule.ps1 to refresh Scheduled Tasks"
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ScheduleScript -ConfigPath $ConfigPath
        if ($LASTEXITCODE -ne 0) { Log "WARN: schedule.ps1 exited $LASTEXITCODE — tasks may need manual re-registration" }
    } catch { Log "WARN: schedule.ps1 invocation failed: $($_.Exception.Message)" }
}

# ---- Cleanup -------------------------------------------------------------
try { Remove-Item -Path $tmpZip -Force -ErrorAction SilentlyContinue } catch {}
try { Remove-Item -Path $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue } catch {}

Write-Host "✓ Updated $currentVersion -> $targetVersion" -ForegroundColor Green
Log "=== update complete: $currentVersion -> $targetVersion ==="
exit 0
