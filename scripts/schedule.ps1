# ============================================================================
# schedule.ps1 — Installs Windows Task Scheduler jobs (v2.5.0):
#
#   1. Daily 11:00 AM     → /meetings-digest (lunch pull)
#   2. Daily  4:00 PM     → /meetings-digest (EOD pull)
#   3. Friday 4:30 PM     → /weekly-rollup   (rollup across rollup-enabled buckets)
#
# Auto-update is DEPRECATED as of v2.5.0 (operator decision 2026-06-01): the
# nightly self-update task never fired reliably on domain-locked machines
# (3 AM, machine asleep/locked) and a broken release had no remediation path.
# Updates are now operator-initiated (update.ps1) + surfaced out-of-band. This
# script defensively unregisters any pre-existing AutoUpdate task on re-run.
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

# Bundle prefix — where bootstrap landed the bundle. Heartbeat wrapper lives
# here, not in the live skill install.
$BundlePrefix = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest'
$HeartbeatWrapper = Join-Path $BundlePrefix 'scripts\run-with-heartbeat.ps1'

# Fall back to script location if LOCALAPPDATA copy isn't there yet (e.g.,
# running schedule.ps1 directly from the unpacked source tree).
if (-not (Test-Path $HeartbeatWrapper)) {
    $LocalScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $HeartbeatWrapper = Join-Path $LocalScriptsDir 'run-with-heartbeat.ps1'
}

# ---- Resolve the REAL Python interpreter ----------------------------------
# `Get-Command python` on a stock Windows install resolves to the Microsoft
# Store App Execution Alias in WindowsApps, which requires UWP Desktop Bridge
# infrastructure unavailable in the Task Scheduler process context — it exits
# instantly with HRESULT 0x80070001 and no output. Resolve the real
# interpreter via the official py.exe launcher first, then known install
# paths, and only fall back to PATH (rejecting the WindowsApps alias).
function Resolve-PythonExe {
    # 1. py.exe launcher — the official Python Launcher for Windows
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        try {
            $resolved = (& py.exe -3 -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-Path $resolved.Trim())) {
                return $resolved.Trim()
            }
        } catch {}
    }
    # 2. Known per-user install paths (newest first)
    $programsRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path $programsRoot) {
        $candidate = Get-ChildItem -Path $programsRoot -Filter 'Python3*' -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName 'python.exe' } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1
        if ($candidate) { return $candidate }
    }
    # 3. Last resort: PATH lookup — but reject the WindowsApps alias
    $cmd = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($cmd -and $cmd -notlike '*WindowsApps*') { return $cmd }
    if ($cmd -and $cmd -like '*WindowsApps*') {
        Write-Warn "Ignoring WindowsApps python alias ($cmd) — it cannot run under Task Scheduler."
    }
    return $null
}

$PythonExe = Resolve-PythonExe
if (-not $PythonExe) {
    Write-Host "✗ Could not resolve a real Python interpreter (py.exe launcher absent, no per-user install, only the WindowsApps alias on PATH). Install Python from python.org and re-run." -ForegroundColor Red
    exit 1
}
Write-Ok "Python: $PythonExe"

$LogDir = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest\logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
# Wrapper-level failures (bad exit codes, ping errors) are logged here so a
# silently-failing scheduled task leaves a trail.
$WrapperLog = Join-Path $LogDir 'wrapper.log'

# ---- Load config (best-effort): heartbeat + auto-update-enabled ----------
$heartbeatBase = 'https://hc-ping.com'
$checkLunch = ''
$checkEod = ''
$checkRollup = ''
$autoUpdateEnabled = $false   # DEPRECATED — default off; honored only if a legacy config explicitly re-enables it

if (Test-Path $ConfigPath) {
    try {
        $cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        if ($cfg.gallant_heartbeat) {
            if ($cfg.gallant_heartbeat.ping_base_url) { $heartbeatBase = $cfg.gallant_heartbeat.ping_base_url }
            if ($cfg.gallant_heartbeat.checks) {
                if ($cfg.gallant_heartbeat.checks.lunch)  { $checkLunch  = [string]$cfg.gallant_heartbeat.checks.lunch }
                if ($cfg.gallant_heartbeat.checks.eod)    { $checkEod    = [string]$cfg.gallant_heartbeat.checks.eod }
                if ($cfg.gallant_heartbeat.checks.rollup) { $checkRollup = [string]$cfg.gallant_heartbeat.checks.rollup }
            }
        }
        if ($cfg.gallant_auto_update -and $cfg.gallant_auto_update.enabled -eq $true) {
            $autoUpdateEnabled = $true
        }
    } catch {
        Write-Warn "Could not parse config from $ConfigPath — tasks will register without heartbeat"
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
        # powershell -File run-with-heartbeat.ps1 -CheckId X -PingBaseUrl Y -LogPath Z <inner-command> <args>
        # NO `--` separator: under `-File`, `--` binds as a positional value, not a
        # stop-parse token. The wrapper uses PositionalBinding=$false + RestArgs to
        # collect the inner command correctly.
        $wrappedArgs = @(
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', "`"$HeartbeatWrapper`"",
            '-CheckId', "`"$CheckId`"",
            '-PingBaseUrl', "`"$heartbeatBase`"",
            '-LogPath', "`"$WrapperLog`"",
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

# ---- Clean up legacy + deprecated task names ------------------------------
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
# Auto-update is deprecated — defensively remove the task unless a legacy
# config explicitly re-enables it (so upgrading from <=v2.4.x cleanly drops it).
if (-not $autoUpdateEnabled) {
    if (Get-ScheduledTask -TaskName 'PlaudMeetingsDigest_AutoUpdate' -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName 'PlaudMeetingsDigest_AutoUpdate' -Confirm:$false
        Write-Warn "Removed deprecated auto-update task (PlaudMeetingsDigest_AutoUpdate). Updates are now operator-initiated — run update.ps1."
    }
}

# ---- Triggers --------------------------------------------------------------
# Schedule matches digest-config.template.json (lunch 11:00, eod 16:00, rollup Fri 16:30).
$lunchTrigger  = New-ScheduledTaskTrigger -Daily -At 11:00AM
$eodTrigger    = New-ScheduledTaskTrigger -Daily -At 4:00PM

# Anchor the weekly rollup StartBoundary to the NEXT actual Friday after
# install. Without this, installing mid-week sets the StartBoundary to "today
# at 16:30"; Windows fires it once on that boundary, then computes the next
# occurrence a full week out — skipping the first real Friday.
function Get-NextWeekday {
    param([datetime]$From, [System.DayOfWeek]$Weekday)
    $daysUntil = ([int]$Weekday - [int]$From.DayOfWeek + 7) % 7
    if ($daysUntil -eq 0) { $daysUntil = 7 }  # if today IS the weekday, use next week's
    return $From.Date.AddDays($daysUntil)
}
$rollupStart   = (Get-NextWeekday -From (Get-Date) -Weekday ([System.DayOfWeek]::Friday)).AddHours(16).AddMinutes(30)
$fridayTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At $rollupStart

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

# ---- Register the three runtime tasks ------------------------------------
Register-DigestTask -TaskName 'PlaudMeetingsDigest_Lunch'  -Description 'Plaud Meetings Digest — lunch run'      -Trigger $lunchTrigger  -Action $lunchAction
Register-DigestTask -TaskName 'PlaudMeetingsDigest_EOD'    -Description 'Plaud Meetings Digest — EOD run'        -Trigger $eodTrigger    -Action $eodAction
Register-DigestTask -TaskName 'PlaudMeetingsDigest_Rollup' -Description 'Plaud Meetings Digest — weekly rollup' -Trigger $fridayTrigger -Action $rollupAction

Write-Host ""
Write-Ok "Three Task Scheduler jobs installed (auto-update deprecated)."
Write-Host "  Lunch:  Daily 11:00 AM    (PlaudMeetingsDigest_Lunch)"
Write-Host "  EOD:    Daily  4:00 PM    (PlaudMeetingsDigest_EOD)"
Write-Host "  Rollup: $($rollupStart.ToString('ddd MMM d')) 4:30 PM, then weekly (PlaudMeetingsDigest_Rollup)"
Write-Host ""
Write-Host "  Logs: $LogDir"
Write-Host ""
if ($checkLunch -or $checkEod -or $checkRollup) {
    Write-Ok "Heartbeat: wrapping enabled (base: $heartbeatBase)"
} else {
    Write-Warn "Heartbeat: no check IDs configured — operator will not be alerted to silent failures"
}
Write-Host ""
Write-Host "Updates:       operator-initiated — run update.ps1 (auto-update deprecated in v2.5.0)"
Write-Host "Verify:        Get-ScheduledTask -TaskName 'PlaudMeetingsDigest_*'"
Write-Host "Test a run:    Start-ScheduledTask -TaskName 'PlaudMeetingsDigest_Lunch'"
Write-Host "Disable one:   Disable-ScheduledTask -TaskName 'PlaudMeetingsDigest_Rollup'"
