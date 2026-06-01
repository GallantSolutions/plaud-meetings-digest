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
#       -LogPath "C:\...\logs\wrapper.log" `
#       python.exe digest-runner.py --skill meetings-digest --source lunch
#
# Every token after the named parameters is the wrapped command + its args,
# collected by $RestArgs. There is NO `--` separator: under `powershell.exe
# -File`, `--` binds as a positional param value, not a stop-parse token, so
# it must be omitted (and PositionalBinding=$false keeps the named params
# name-only so the executable lands in $RestArgs, not $BundlePrefix).
#
# Ping flow:
#   1. GET <base>/<id>/start         (let HC know the job started)
#   2. Run the command, capture exit code
#   3. GET <base>/<id>/<exit-code>   (0 = success; normalized to 0-255)
#
# Heartbeat pings are best-effort. A failed ping NEVER aborts the wrapped
# command — if the network is down, the job still runs and the operator just
# sees a missed-ping alert on the next scheduled window.
# ============================================================================

#Requires -Version 5.1

[CmdletBinding(PositionalBinding=$false)]
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

function Write-WrapperLog {
    param([string]$Message)
    if ($LogPath) {
        try { "[$(Get-Date -Format o)] $Message" | Out-File -FilePath $LogPath -Append -Encoding UTF8 } catch {}
    }
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
        Write-WrapperLog "heartbeat ping failed ($url): $($_.Exception.Message)"
    }
}

# Healthchecks.io only accepts an exit-code suffix in the 0-255 range. A raw
# Windows HRESULT (e.g. 2147942401 from a WindowsApps alias) is a 9-digit
# value HC rejects (4xx), which would silently drop the outcome ping and the
# operator would never be alerted. Normalize: 0 → success, anything else → 1.
function Get-HcSuffix {
    param([int]$Code)
    if ($Code -eq 0) { return '0' }
    if ($Code -lt 0 -or $Code -gt 255) { return '1' }
    return $Code.ToString()
}

# ---- Start ping ----------------------------------------------------------
Send-HeartbeatPing -Suffix 'start'

# ---- Run the wrapped command --------------------------------------------
$exitCode = 0
if (-not $RestArgs -or $RestArgs.Count -eq 0) {
    Write-WrapperLog "no command supplied — nothing to run"
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
    Write-WrapperLog "wrapped command threw: $($_.Exception.Message)"
}

# ---- Outcome ping --------------------------------------------------------
# Normalized to the 0-255 range HC accepts; non-zero triggers the alert.
Send-HeartbeatPing -Suffix (Get-HcSuffix -Code $exitCode)

exit $exitCode
