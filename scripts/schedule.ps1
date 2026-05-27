# ============================================================================
# schedule.ps1 — Installs FOUR Windows Task Scheduler jobs (v2.2.0):
#
#   1. Daily 11:00 AM     → /meetings-digest (lunch pull)
#   2. Daily  4:00 PM     → /meetings-digest (EOD pull)
#   3. Friday 4:30 PM     → /weekly-rollup   (rollup across all rollup-enabled buckets)
#   4. Daily  3:00 AM     → auto-update      (pulls latest GitHub release)
#
# Every task is wrapped in run-with-heartbeat.ps1 — pings Healthchecks.io
# before/after so the operator gets alerted when a run misses its window.
#
# Tasks run as the current user. They wake the machine if asleep (WakeToRun)
# and tolerate missed runs (StartWhenAvailable).
# ============================================================================

#Requires -Version 5.1

param(
    [Parameter(Mandatory=$false)]
    [string]$ConfigPath = (Join-Path $HOME '.claude\skills\meetings-digest\config.json')
)

$ErrorActionPreference = 'Stop'

function Write-Ok   { param([string]$Text) Write-Host "✓ $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text) Write-Host "⚠ $Text" -ForegroundColor Yellow }

# ---- Resolve paths --------------------------------------------------------
$RunnerScript = Join-Path $HOME '.claude\skills\meetings-digest\scripts\digest-runner.py'
if (-not (Test-Path $RunnerScript)) {
    Write-Host "✗ Runner not found at $RunnerScript. Run install.ps1 first." -ForegroundColor Red
    exit 1
}

# Bundle prefix — where bootstrap landed the bundle. Heartbeat wrapper +
# auto-update script live here, not in the live skill install.
$BundlePrefix = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest'
$HeartbeatWrapper = Join-Path $BundlePrefix 'scripts\run-with-heartbeat.ps1'
$AutoUpdateScript = Join-Path $BundlePrefix 'scripts\auto-update.ps1'

# Fall back to script location if LOCALAPPDATA copy isn't there yet (e.g.,
# running schedule.ps1 directly from the unpacked source tree).
if (-not (Test-Path $HeartbeatWrapper)) {
    $LocalScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $HeartbeatWrapper = Join-Path $LocalScriptsDir 'run-with-heartbeat.ps1'
    $AutoUpdateScript = Join-Path $LocalScriptsDir 'auto-update.ps1'
}

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Host "✗ python not on PATH. Cannot schedule." -ForegroundColor Red
    exit 1
}

$LogDir = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest\logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# ---- Load heartbeat config (best-effort) ---------------------------------
$heartbeatBase = 'https://hc-ping.com'
$checkLunch = ''
$checkEod = ''
$checkRollup = ''
$checkAutoUpdate = ''

if (Test-Path $ConfigPath) {
    try {
        $cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        if ($cfg.gallant_heartbeat) {
            if ($cfg.gallant_heartbeat.ping_base_url) { $heartbeatBase = $cfg.gallant_heartbeat.ping_base_url }
            if ($cfg.gallant_heartbeat.checks) {
                if ($cfg.gallant_heartbeat.checks.lunch)       { $checkLunch       = [string]$cfg.gallant_heartbeat.checks.lunch }
                if ($cfg.gallant_heartbeat.checks.eod)         { $checkEod         = [string]$cfg.gallant_heartbeat.checks.eod }
                if ($cfg.gallant_heartbeat.checks.rollup)      { $checkRollup      = [string]$cfg.gallant_heartbeat.checks.rollup }
                if ($cfg.gallant_heartbeat.checks.auto_update) { $checkAutoUpdate  = [string]$cfg.gallant_heartbeat.checks.auto_update }
            }
        }
    } catch {
        Write-Warn "Could not parse heartbeat config from $ConfigPath — tasks will register without heartbeat"
    }
}

# ---- Common task settings -------------------------------------------------
$CommonSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# ---- Build a heartbeat-wrapped action -------------------------------------
function Build-WrappedAction {
    param(
        [string]$CheckId,
        [string]$InnerCommand,
        [string[]]$InnerArgs
    )

    if ($HeartbeatWrapper -and (Test-Path $HeartbeatWrapper) -and $CheckId) {
        # Wrap: powershell -File run-with-heartbeat.ps1 -CheckId X -PingBaseUrl Y -- inner-command args
        $wrappedArgs = @(
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', "`"$HeartbeatWrapper`"",
            '-CheckId', "`"$CheckId`"",
            '-PingBaseUrl', "`"$heartbeatBase`"",
            '--',
            "`"$InnerCommand`""
        )
        foreach ($a in $InnerArgs) { $wrappedArgs += "`"$a`"" }
        return New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ($wrappedArgs -join ' ')
    } else {
        # No heartbeat — direct invocation
        return New-ScheduledTaskAction -Execute $InnerCommand -Argument (($InnerArgs | ForEach-Object { "`"$_`"" }) -join ' ')
    }
}

# ---- Helper to (re)register a task ----------------------------------------
function Register-DigestTask {
    param(
        [string]$TaskName,
        [string]$Description,
        # Triggers come from New-ScheduledTaskTrigger which returns [CimInstance].
        # Untyped to support PowerShell 7 (no PSScheduledJob module).
        $Trigger,
        $Action
    )

    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action   $Action `
        -Trigger  $Trigger `
        -Settings $CommonSettings `
        -Description $Description | Out-Null

    Write-Ok "Registered task: $TaskName"
}

# ---- Clean up legacy task names ------------------------------------------
$LegacyTaskNames = @(
    'PlaudMeetingsDigest_Friday',
    'PlaudMeetingsDigest_Weekly'
)
foreach ($legacy in $LegacyTaskNames) {
    if (Get-ScheduledTask -TaskName $legacy -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $legacy -Confirm:$false
        Write-Warn "Removed legacy task: $legacy"
    }
}

# ---- Triggers --------------------------------------------------------------
# Schedule matches digest-config.template.json (lunch 11:00, eod 16:00, rollup Fri 16:30).
$lunchTrigger  = New-ScheduledTaskTrigger -Daily -At 11:00AM
$eodTrigger    = New-ScheduledTaskTrigger -Daily -At 4:00PM
$fridayTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 4:30PM
$updateTrigger = New-ScheduledTaskTrigger -Daily -At 3:00AM

# ---- Actions (heartbeat-wrapped) -----------------------------------------
$lunchAction = Build-WrappedAction `
    -CheckId $checkLunch `
    -InnerCommand $PythonExe `
    -InnerArgs @($RunnerScript, '--skill', 'meetings-digest', '--source', 'lunch')

$eodAction = Build-WrappedAction `
    -CheckId $checkEod `
    -InnerCommand $PythonExe `
    -InnerArgs @($RunnerScript, '--skill', 'meetings-digest', '--source', 'eod')

$rollupAction = Build-WrappedAction `
    -CheckId $checkRollup `
    -InnerCommand $PythonExe `
    -InnerArgs @($RunnerScript, '--skill', 'weekly-rollup', '--source', 'rollup')

$updateAction = Build-WrappedAction `
    -CheckId $checkAutoUpdate `
    -InnerCommand 'powershell.exe' `
    -InnerArgs @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $AutoUpdateScript, '-ConfigPath', $ConfigPath)

# ---- Register all four ---------------------------------------------------
Register-DigestTask -TaskName 'PlaudMeetingsDigest_Lunch'      -Description 'Plaud Meetings Digest — lunch run'  -Trigger $lunchTrigger  -Action $lunchAction
Register-DigestTask -TaskName 'PlaudMeetingsDigest_EOD'        -Description 'Plaud Meetings Digest — EOD run'    -Trigger $eodTrigger    -Action $eodAction
Register-DigestTask -TaskName 'PlaudMeetingsDigest_Rollup'     -Description 'Plaud Meetings Digest — weekly rollup' -Trigger $fridayTrigger -Action $rollupAction
Register-DigestTask -TaskName 'PlaudMeetingsDigest_AutoUpdate' -Description 'Plaud Meetings Digest — nightly auto-update' -Trigger $updateTrigger -Action $updateAction

Write-Host ""
Write-Ok "Four Task Scheduler jobs installed."
Write-Host "  Lunch:       Daily 11:00 AM    (PlaudMeetingsDigest_Lunch)"
Write-Host "  EOD:         Daily  4:00 PM    (PlaudMeetingsDigest_EOD)"
Write-Host "  Rollup:      Friday 4:30 PM    (PlaudMeetingsDigest_Rollup)"
Write-Host "  Auto-update: Daily  3:00 AM    (PlaudMeetingsDigest_AutoUpdate)"
Write-Host ""
Write-Host "  Logs: $LogDir"
Write-Host ""
if ($checkLunch -or $checkEod -or $checkRollup -or $checkAutoUpdate) {
    Write-Ok "Heartbeat: wrapping enabled (base: $heartbeatBase)"
} else {
    Write-Warn "Heartbeat: no check IDs configured — operator will not be alerted to silent failures"
}
Write-Host ""
Write-Host "Verify:        Get-ScheduledTask -TaskName 'PlaudMeetingsDigest_*'"
Write-Host "Test a run:    Start-ScheduledTask -TaskName 'PlaudMeetingsDigest_Lunch'"
Write-Host "Disable one:   Disable-ScheduledTask -TaskName 'PlaudMeetingsDigest_Rollup'"
