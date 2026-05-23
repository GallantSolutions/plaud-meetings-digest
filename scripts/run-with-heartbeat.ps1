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

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$RestArgs
)

$ErrorActionPreference = 'Continue'  # do NOT stop on ping failures

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

# ---- Outcome ping --------------------------------------------------------
# Healthchecks accepts /<id>/<exit-code> directly: 0 is success, non-zero is
# treated as failure and triggers the configured notification channel.
Send-HeartbeatPing -Suffix $exitCode.ToString()

exit $exitCode
