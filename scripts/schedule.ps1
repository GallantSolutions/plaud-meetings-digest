# ============================================================================
# schedule.ps1 — Installs THREE Windows Task Scheduler jobs:
#
#   1. Daily 12:30 PM     → /meetings-digest (lunch pull)
#   2. Daily  5:00 PM     → /meetings-digest (EOD pull)
#   3. Friday 5:30 PM     → /weekly-rollup   (Kingsway Pharma rollup)
#
# Tasks run as the current user. They wake the machine if asleep (BatteryWake)
# and tolerate missed runs (StartWhenAvailable).
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

function Write-Ok   { param([string]$Text) Write-Host "✓ $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text) Write-Host "⚠ $Text" -ForegroundColor Yellow }

$RunnerScript = Join-Path $HOME '.claude\skills\meetings-digest\scripts\digest-runner.py'
if (-not (Test-Path $RunnerScript)) {
    Write-Host "✗ Runner not found at $RunnerScript. Run install.ps1 first." -ForegroundColor Red
    exit 1
}

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Host "✗ python not on PATH. Cannot schedule." -ForegroundColor Red
    exit 1
}

$LogDir = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest\logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# ---- Common task settings -------------------------------------------------
$CommonSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# ---- Helper to (re)register a task ----------------------------------------
function Register-DigestTask {
    param(
        [string]$TaskName,
        [string]$Skill,
        [string]$Source,
        [Microsoft.PowerShell.ScheduledJob.ScheduledJobTrigger]$Trigger
    )

    # Unregister any prior version with this name
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $action = New-ScheduledTaskAction `
        -Execute $PythonExe `
        -Argument "`"$RunnerScript`" --skill $Skill --source $Source"

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action   $action `
        -Trigger  $Trigger `
        -Settings $CommonSettings `
        -Description "Plaud Meetings Digest — $Source run" | Out-Null

    Write-Ok "Registered task: $TaskName"
}

# Clean up legacy task names from prior versions if they exist
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
# Daily 12:30 PM
$lunchTrigger = New-ScheduledTaskTrigger -Daily -At 12:30PM

# Daily 5:00 PM
$eodTrigger = New-ScheduledTaskTrigger -Daily -At 5:00PM

# Friday 5:30 PM
$fridayTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 5:30PM

# ---- Register all three ---------------------------------------------------
Register-DigestTask -TaskName 'PlaudMeetingsDigest_Lunch'  -Skill 'meetings-digest' -Source 'lunch' -Trigger $lunchTrigger
Register-DigestTask -TaskName 'PlaudMeetingsDigest_EOD'    -Skill 'meetings-digest' -Source 'eod'   -Trigger $eodTrigger
Register-DigestTask -TaskName 'PlaudMeetingsDigest_Rollup' -Skill 'weekly-rollup'   -Source 'rollup' -Trigger $fridayTrigger

Write-Host ""
Write-Ok "Three Task Scheduler jobs installed."
Write-Host "  Lunch:  Daily 12:30 PM   (PlaudMeetingsDigest_Lunch)"
Write-Host "  EOD:    Daily  5:00 PM   (PlaudMeetingsDigest_EOD)"
Write-Host "  Rollup: Friday 5:30 PM   (PlaudMeetingsDigest_Rollup)"
Write-Host ""
Write-Host "  Logs:   $LogDir"
Write-Host ""
Write-Host "Verify:        Get-ScheduledTask -TaskName 'PlaudMeetingsDigest_*'"
Write-Host "Test a run:    Start-ScheduledTask -TaskName 'PlaudMeetingsDigest_Lunch'"
Write-Host "Disable one:   Disable-ScheduledTask -TaskName 'PlaudMeetingsDigest_Rollup'"
