# ============================================================================
# auto-update.ps1 — Gallant standard auto-updater (Windows)
# ============================================================================
# Checks GitHub Releases for a newer version of the bundle. If found:
#   1. Snapshots the current bundle to <prefix>/.versions/<old-tag>/
#   2. Downloads + extracts the new release zip
#   3. Replaces the bundle files (preserves config.json)
#   4. Re-runs scripts/schedule.ps1 to refresh Scheduled Tasks
#   5. Updates version.txt
#
# Pinned versions: if config.gallant_auto_update.pinned_version is set, the
# updater only updates to that exact tag (or does nothing if already there).
#
# Intentionally silent — no Read-Host, no console prompts. Designed to run
# from a Scheduled Task at 3:00 AM local time. All output goes to the log.
#
# Heartbeat: this script does NOT emit heartbeat pings itself — it's
# expected to be wrapped by run-with-heartbeat.ps1 via the Scheduled Task.
# ============================================================================

#Requires -Version 5.1

param(
    [Parameter(Mandatory=$false)]
    [string]$BundlePrefix = '',

    [Parameter(Mandatory=$false)]
    [string]$ConfigPath = '',

    [Parameter(Mandatory=$false)]
    [string]$Repo = '',

    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# ---- Resolve defaults from config if not passed --------------------------
if (-not $BundlePrefix) {
    $BundlePrefix = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest'
}
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $HOME '.claude\skills\meetings-digest\config.json'
}

$LogDir = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest\logs'
$LogPath = Join-Path $LogDir 'auto-update.log'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Log {
    param([string]$Message)
    $line = "[$(Get-Date -Format o)] $Message"
    $line | Out-File -FilePath $LogPath -Append -Encoding UTF8
    Write-Host $line
}

Log "=== auto-update.ps1 starting ==="
Log "Bundle prefix: $BundlePrefix"
Log "Config path:   $ConfigPath"

# ---- Load config to resolve repo + pinned version ------------------------
if (-not (Test-Path $ConfigPath)) {
    Log "ERROR: config not found at $ConfigPath — cannot auto-update without it"
    exit 1
}

try {
    $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
} catch {
    Log "ERROR: config JSON invalid: $($_.Exception.Message)"
    exit 1
}

$updateConfig = $config.gallant_auto_update
if (-not $updateConfig) {
    Log "ERROR: config has no gallant_auto_update block — bundle wasn't installed with the install-pattern"
    exit 1
}

if (-not $updateConfig.enabled) {
    Log "Auto-update disabled in config — exiting cleanly"
    exit 0
}

if (-not $Repo) { $Repo = $updateConfig.repo }
if (-not $Repo) {
    Log "ERROR: no repo configured (config.gallant_auto_update.repo missing)"
    exit 1
}

$pinned = $updateConfig.pinned_version
$channel = if ($updateConfig.channel) { $updateConfig.channel } else { 'latest' }

# ---- Read current version --------------------------------------------------
$VersionFile = Join-Path $BundlePrefix 'version.txt'
$currentVersion = ''
if (Test-Path $VersionFile) {
    $currentVersion = (Get-Content $VersionFile -Raw).Trim()
}
Log "Current version: '$currentVersion'"

# ---- Resolve target version from GitHub Releases -------------------------
$targetVersion = ''
if ($pinned) {
    $targetVersion = $pinned
    Log "Pinned to: $targetVersion"
} else {
    Log "Channel: $channel — resolving via GitHub Releases API"
    try {
        if ($channel -eq 'latest') {
            $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -UseBasicParsing -TimeoutSec 30
        } else {
            $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/tags/$channel" -UseBasicParsing -TimeoutSec 30
        }
        $targetVersion = $release.tag_name
    } catch {
        Log "ERROR: could not resolve target version: $($_.Exception.Message)"
        exit 1
    }
}
Log "Target version: $targetVersion"

if ($targetVersion -eq $currentVersion) {
    Log "Already on $targetVersion — nothing to do"
    exit 0
}

if ($DryRun) {
    Log "DRY RUN: would update $currentVersion -> $targetVersion"
    exit 0
}

# ---- Snapshot current bundle ---------------------------------------------
if ($currentVersion) {
    $snapshotDir = Join-Path $BundlePrefix ".versions\$currentVersion"
    if (Test-Path $snapshotDir) {
        Log "Snapshot already exists at $snapshotDir — leaving it in place"
    } else {
        Log "Snapshotting current bundle to $snapshotDir"
        try {
            New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null
            # Copy everything except .versions (would recurse) and tmp scratch
            Get-ChildItem -Path $BundlePrefix -Force | Where-Object { $_.Name -notin @('.versions', 'logs') } | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination $snapshotDir -Recurse -Force
            }
        } catch {
            Log "WARN: snapshot failed ($($_.Exception.Message)) — proceeding with update anyway"
        }
    }
}

# ---- Download + extract new release --------------------------------------
$tmpZip = Join-Path $env:TEMP "gallant-update-$([System.IO.Path]::GetRandomFileName()).zip"
$tmpExtract = Join-Path $env:TEMP "gallant-update-extract-$([System.IO.Path]::GetRandomFileName())"

$zipUrl = "https://github.com/$Repo/archive/refs/tags/$targetVersion.zip"
Log "Downloading $zipUrl"
try {
    Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing -TimeoutSec 300
} catch {
    Log "ERROR: download failed: $($_.Exception.Message)"
    exit 1
}

Log "Extracting to $tmpExtract"
New-Item -ItemType Directory -Path $tmpExtract -Force | Out-Null
try {
    Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force
} catch {
    Log "ERROR: extract failed: $($_.Exception.Message)"
    exit 1
}

$extracted = Get-ChildItem -Path $tmpExtract -Directory | Select-Object -First 1
if (-not $extracted) {
    Log "ERROR: extracted folder not found"
    exit 1
}

# ---- Replace bundle files (preserve client-customized parts) -------------
# Files/folders we OVERWRITE from the new release:
#   - install.ps1, install.sh, bootstrap.ps1, bootstrap.sh, uninstall.*
#   - README.md, OPERATOR-INSTALL-GUIDE.md, docs/
#   - scripts/ (all)
#   - skills/<*>/SKILL.md  (skill bodies update, but installed copies in
#     ~/.claude/skills/ are updated separately via the install-script flow)
#   - config/*.template.json  (template only; live config.json untouched)
#
# Things we DO NOT touch:
#   - <prefix>/.versions/  (rollback snapshots)
#   - <prefix>/logs/       (audit trail)
#   - ~/.claude/skills/meetings-digest/config.json (client's live config)
#   - ~/.claude/skills/meetings-digest/state/      (dedup state)

Log "Replacing bundle files at $BundlePrefix"
try {
    Get-ChildItem -Path $extracted.FullName -Force | ForEach-Object {
        $destPath = Join-Path $BundlePrefix $_.Name
        if (Test-Path $destPath) {
            Remove-Item -Path $destPath -Recurse -Force
        }
        Copy-Item -Path $_.FullName -Destination $destPath -Recurse -Force
    }
} catch {
    Log "ERROR: file replacement failed: $($_.Exception.Message)"
    exit 1
}

# ---- Push updated skill bodies into ~/.claude/skills/ --------------------
# The bundle has skills/<name>/SKILL.md + scripts/*.py — the live install
# expects them at ~/.claude/skills/<name>/SKILL.md + scripts/. Copy over.
$liveSkillsRoot = Join-Path $HOME '.claude\skills'
if (Test-Path (Join-Path $BundlePrefix 'skills')) {
    Get-ChildItem -Path (Join-Path $BundlePrefix 'skills') -Directory | ForEach-Object {
        $liveSkill = Join-Path $liveSkillsRoot $_.Name
        if (Test-Path $liveSkill) {
            $sourceSkillMd = Join-Path $_.FullName 'SKILL.md'
            if (Test-Path $sourceSkillMd) {
                Copy-Item -Path $sourceSkillMd -Destination (Join-Path $liveSkill 'SKILL.md') -Force
                Log "Updated SKILL.md for $($_.Name)"
            }
        }
    }
}

# Copy scripts/ into the meetings-digest live install (where the
# Scheduled Tasks point). Build-specific — the install-pattern scaffold
# leaves this targeting plaud-meetings-digest; adjust per-build if a
# different skill is the runtime target.
#
# v2.4.1 fix: copy the FULL scripts/ tree (including subpackages like tray/),
# not just top-level *.py. The earlier *.py-only filter shipped tray_bridge.py
# but left the tray/ subpackage behind, breaking tray_bridge's import on
# Friday rollup day. Exclusions match install.ps1 + install_tray.ps1.
$liveScripts = Join-Path $liveSkillsRoot 'meetings-digest\scripts'
if (Test-Path $liveScripts) {
    $bundleScripts = Join-Path $BundlePrefix 'scripts'
    $scriptExclude = @('preview.html', 'README.md', 'install_tray.ps1', '__pycache__')

    # Top-level *.py files
    Get-ChildItem -Path $bundleScripts -Filter '*.py' -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $liveScripts -Force
    }

    # Subpackages — currently just tray/. Iterate so future subpackages
    # propagate without editing this script.
    Get-ChildItem -Path $bundleScripts -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $destSubdir = Join-Path $liveScripts $_.Name
        if (Test-Path $destSubdir) { Remove-Item -Recurse -Force $destSubdir }
        Copy-Item -Recurse -Force -Path $_.FullName -Destination $destSubdir -Exclude $scriptExclude
        # -Exclude on Copy-Item only filters top level — sweep nested __pycache__.
        Get-ChildItem -Path $destSubdir -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }

    Log "Updated Python helpers + subpackages in $liveScripts"
}

# v2.4.1: also (re)run install_tray.ps1 if the bundle ships one. install_tray.ps1
# is idempotent — re-running upgrades deps + refreshes the Startup shortcut + only
# launches the tray if it isn't already running. Wrapped in try/catch so a tray
# install failure doesn't break the auto-update itself (the rollup pipeline still
# works without the tray; the tray is a UI nice-to-have on top).
$bundleTrayInstaller = Join-Path $BundlePrefix 'scripts\tray\install_tray.ps1'
if (Test-Path $bundleTrayInstaller) {
    Log "Running install_tray.ps1 to (re)install the system-tray widget"
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bundleTrayInstaller -Quiet
        if ($LASTEXITCODE -ne 0) {
            Log "WARN: install_tray.ps1 exited with $LASTEXITCODE — tray may not be running. Re-run manually: $bundleTrayInstaller"
        } else {
            Log "Tray widget install/refresh complete"
        }
    } catch {
        Log "WARN: install_tray.ps1 invocation raised: $($_.Exception.Message). Tray may not be running."
    }
}

# ---- Update version stamp ------------------------------------------------
Set-Content -Path $VersionFile -Value $targetVersion -Encoding UTF8
Log "Wrote version.txt = $targetVersion"

# ---- Write update marker (auto-rollback safety net, v2.2.3+) -------------
# The heartbeat wrapper checks this file when a wrapped command fails non-
# zero. If the update was recent (< 24h) AND rolled_back is false, the
# wrapper auto-restores the previous version from .versions/<from_version>/.
# One-shot — the wrapper sets rolled_back: true so subsequent failures
# don't repeat the rollback.
$updateMarker = Join-Path $BundlePrefix '.last-update.json'
$markerData = [ordered]@{
    from_version = $currentVersion
    to_version   = $targetVersion
    updated_at   = (Get-Date).ToUniversalTime().ToString('o')
    rolled_back  = $false
} | ConvertTo-Json
Set-Content -Path $updateMarker -Value $markerData -Encoding UTF8
Log "Wrote update marker: $updateMarker"

# ---- Re-register Scheduled Tasks (in case task definitions changed) ------
$ScheduleScript = Join-Path $BundlePrefix 'scripts\schedule.ps1'
if (Test-Path $ScheduleScript) {
    Log "Re-running schedule.ps1 to refresh Scheduled Tasks"
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ScheduleScript -ConfigPath $ConfigPath
        if ($LASTEXITCODE -ne 0) {
            Log "WARN: schedule.ps1 exited with $LASTEXITCODE — tasks may need manual re-registration"
        }
    } catch {
        Log "WARN: schedule.ps1 invocation failed: $($_.Exception.Message)"
    }
}

# ---- Cleanup tmp ---------------------------------------------------------
try { Remove-Item -Path $tmpZip -Force -ErrorAction SilentlyContinue } catch {}
try { Remove-Item -Path $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue } catch {}

Log "=== auto-update complete: $currentVersion -> $targetVersion ==="
exit 0
