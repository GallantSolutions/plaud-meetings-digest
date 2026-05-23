# ============================================================================
# run-with-heartbeat.ps1 — Gallant standard heartbeat wrapper (Windows)
# ============================================================================
# Wraps any command, pings Healthchecks.io before/after the wrapped run.
#
# Usage (from a Scheduled Task action):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass `
#       -File "C:\path\to\run-with-heartbeat.ps1" `
#       -CheckId "uuid-from-healthchecks" `
#       -PingBaseUrl "https://hc-ping.com" `
#       -- python.exe digest-runner.py --skill meetings-digest --source lunch
#
# Anything after the -- is treated as the wrapped command + its args.
#
# Ping flow:
#   1. GET <base>/<id>/start         (let HC know the job started)
#   2. Run the command, capture exit code
#   3. GET <base>/<id>/<exit-code>   (0 = success, anything else = fail)
#
# Heartbeat pings are best-effort. A failed ping NEVER aborts the wrapped
# command — if the network is down, the job still runs successfully and the
# operator just sees a missed-ping alert on the next scheduled window.
# ============================================================================

#Requires -Version 5.1

param(
    [Parameter(Mandatory=$true)]
    [string]$CheckId,

    [Parameter(Mandatory=$false)]
    [string]$PingBaseUrl = 'https://hc-ping.com',

    [Parameter(Mandatory=$false)]
    [string]$LogPath = '',

    [Parameter(Mandatory=$false)]
    [string]$BundlePrefix = '',

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$RestArgs
)

$ErrorActionPreference = 'Continue'  # do NOT stop on ping failures

# Default the bundle prefix to the standard install location if not supplied
if (-not $BundlePrefix) {
    $BundlePrefix = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest'
}

function Send-HeartbeatPing {
    param([string]$Suffix = '')
    if (-not $CheckId -or $CheckId -eq 'null' -or $CheckId -eq '') {
        return  # No check configured — skip silently.
    }
    $url = "$PingBaseUrl/$CheckId"
    if ($Suffix) { $url = "$url/$Suffix" }
    try {
        Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 10 -UseBasicParsing | Out-Null
    } catch {
        if ($LogPath) {
            try { "[$(Get-Date -Format o)] heartbeat ping failed ($url): $($_.Exception.Message)" | Out-File -FilePath $LogPath -Append -Encoding UTF8 } catch {}
        }
    }
}

function Write-RollbackLog {
    param([string]$Message)
    $rollbackLog = Join-Path $BundlePrefix 'logs\auto-rollback.log'
    try {
        $logDir = Split-Path -Parent $rollbackLog
        if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
        "[$(Get-Date -Format o)] $Message" | Out-File -FilePath $rollbackLog -Append -Encoding UTF8
    } catch {}
}

function Invoke-AutoRollbackIfWarranted {
    <#
    Called when the wrapped command exited non-zero. Checks the update
    marker; if the most-recent auto-update was within 24h AND we haven't
    already rolled back, restores the previous version's bundle snapshot
    and pings the heartbeat with a special marker.
    #>
    $marker = Join-Path $BundlePrefix '.last-update.json'
    if (-not (Test-Path $marker)) { return $false }

    try {
        $markerData = Get-Content $marker -Raw | ConvertFrom-Json
    } catch {
        Write-RollbackLog "marker exists but parse failed: $($_.Exception.Message)"
        return $false
    }

    if ($markerData.rolled_back -eq $true) {
        Write-RollbackLog "rollback already executed for this update — skipping"
        return $false
    }

    $fromVersion = $markerData.from_version
    if (-not $fromVersion) {
        Write-RollbackLog "marker has no from_version — cannot rollback"
        return $false
    }

    # Window check: only auto-rollback if the update was recent (<24h)
    try {
        $updatedAt = [DateTime]::Parse($markerData.updated_at)
        $ageHours = ((Get-Date) - $updatedAt).TotalHours
        if ($ageHours -gt 24) {
            Write-RollbackLog "update was $([int]$ageHours)h ago — outside rollback window, skipping"
            return $false
        }
    } catch {
        Write-RollbackLog "could not parse updated_at: $($_.Exception.Message)"
        return $false
    }

    $snapshot = Join-Path $BundlePrefix ".versions\$fromVersion"
    if (-not (Test-Path $snapshot)) {
        Write-RollbackLog "snapshot missing at $snapshot — cannot rollback"
        return $false
    }

    Write-RollbackLog "ROLLING BACK to $fromVersion (snapshot at $snapshot)"

    # Restore snapshot contents over the bundle prefix.
    # Skip .versions/, logs/, .last-update.json (we update the marker after).
    try {
        Get-ChildItem -Path $snapshot -Force | ForEach-Object {
            if ($_.Name -in @('.versions', 'logs', '.last-update.json')) { return }
            $destPath = Join-Path $BundlePrefix $_.Name
            if (Test-Path $destPath) { Remove-Item -Path $destPath -Recurse -Force }
            Copy-Item -Path $_.FullName -Destination $destPath -Recurse -Force
        }

        # Reset version.txt to the rolled-back version
        $vFile = Join-Path $BundlePrefix 'version.txt'
        Set-Content -Path $vFile -Value $fromVersion -Encoding UTF8

        # Mark the marker as rolled back (one-shot guard)
        $markerData | Add-Member -NotePropertyName rolled_back -NotePropertyValue $true -Force
        $markerData | Add-Member -NotePropertyName rolled_back_at -NotePropertyValue (Get-Date -Format o) -Force
        ($markerData | ConvertTo-Json) | Set-Content -Path $marker -Encoding UTF8

        # Re-register Scheduled Tasks from the rolled-back schedule.ps1
        $scheduleScript = Join-Path $BundlePrefix 'scripts\schedule.ps1'
        if (Test-Path $scheduleScript) {
            try {
                $configPath = Join-Path $HOME '.claude\skills\meetings-digest\config.json'
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scheduleScript -ConfigPath $configPath | Out-Null
            } catch {
                Write-RollbackLog "schedule.ps1 re-registration after rollback failed: $($_.Exception.Message)"
            }
        }

        Write-RollbackLog "ROLLBACK COMPLETE — bundle restored to $fromVersion"
        # Special heartbeat ping so the operator knows a rollback happened
        # (Healthchecks renders the suffix in the dashboard event log)
        Send-HeartbeatPing -Suffix 'fail'
        return $true
    } catch {
        Write-RollbackLog "ROLLBACK FAILED: $($_.Exception.Message)"
        return $false
    }
}

# ---- Start ping ----------------------------------------------------------
Send-HeartbeatPing -Suffix 'start'

# ---- Run the wrapped command --------------------------------------------
$exitCode = 0
if (-not $RestArgs -or $RestArgs.Count -eq 0) {
    if ($LogPath) {
        try { "[$(Get-Date -Format o)] no command supplied — nothing to run" | Out-File -FilePath $LogPath -Append -Encoding UTF8 } catch {}
    }
    Send-HeartbeatPing -Suffix '99'
    exit 99
}

$exe = $RestArgs[0]
$exeArgs = if ($RestArgs.Count -gt 1) { $RestArgs[1..($RestArgs.Count - 1)] } else { @() }

try {
    & $exe @exeArgs
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
} catch {
    $exitCode = 99  # wrapper-level failure
    if ($LogPath) {
        try { "[$(Get-Date -Format o)] wrapped command threw: $($_.Exception.Message)" | Out-File -FilePath $LogPath -Append -Encoding UTF8 } catch {}
    }
}

# ---- Auto-rollback (v2.2.3+) --------------------------------------------
# If the wrapped command failed AND we recently auto-updated, restore the
# previous version. This is a self-healing safety net for the failure mode
# where a bad release breaks the install — the client doesn't have to
# notice, the next scheduled run will execute on the rolled-back code.
if ($exitCode -ne 0) {
    $rolledBack = Invoke-AutoRollbackIfWarranted
    if ($rolledBack) {
        # The outcome ping happens inside Invoke-AutoRollbackIfWarranted with
        # a 'fail' suffix so Healthchecks fires the alert AND the dashboard
        # event log captures that a rollback occurred. Don't double-ping.
        exit $exitCode
    }
}

# ---- Outcome ping --------------------------------------------------------
# Healthchecks accepts /<id>/<exit-code> directly: 0 is success, non-zero is
# treated as failure and triggers the configured notification channel.
Send-HeartbeatPing -Suffix $exitCode.ToString()

exit $exitCode
