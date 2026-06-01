# ============================================================================
# report-state.ps1 - Gallant standard field-state reporter (Windows)
# ============================================================================
# Read-only. Captures what is ACTUALLY installed + running on a client machine
# so the operator can reconcile the live build against the canonical release
# and decide whether to converge (run update.ps1) or finalize from the captured
# files.
#
# Counterpart to preflight.ps1: preflight checks the machine BEFORE install;
# report-state captures the build AFTER install, in the field.
#
# What it does:
#   1. Prints a paste-able SUMMARY block (version, file hashes, scheduler
#      health, redacted config, recent log tail) to the console.
#   2. Writes a zip of the actual build files (both script copies + version.txt
#      + a REDACTED config + scheduler dump + log tail + a hash manifest) to
#      -OutDir, so the operator can pull the real file contents back and diff
#      them against the v2.5.0 tag.
#
# It NEVER mutates the install and NEVER lets a secret leave the machine:
# the live config.json (Healthchecks check IDs, any tokens) is redacted before
# anything is written to the zip. The console summary is redacted the same way.
#
# Usage (operator hands this to the client; client runs it):
#   powershell -ExecutionPolicy Bypass -File report-state.ps1
#   powershell -ExecutionPolicy Bypass -File report-state.ps1 -OutDir "$env:USERPROFILE\Desktop"
#
# Then: send the printed zip back to your Gallant operator (paste the SUMMARY
# block into chat, or attach the zip).
# ============================================================================

[CmdletBinding()]
param(
    [string]$OutDir = "$env:USERPROFILE\Desktop"
)

$ErrorActionPreference = 'Continue'

# ---- Install layout (must match install.ps1 / schedule.ps1) ----------------
$SkillDir      = Join-Path $HOME '.claude\skills\meetings-digest'
$SkillScripts  = Join-Path $SkillDir 'scripts'
$ConfigPath    = Join-Path $SkillDir 'config.json'
$BundlePrefix  = Join-Path $env:LOCALAPPDATA 'plaud-meetings-digest'
$BundleScripts = Join-Path $BundlePrefix 'scripts'
$VersionFile   = Join-Path $BundlePrefix 'version.txt'
$LogDir        = Join-Path $BundlePrefix 'logs'
$TrayPrefix    = Join-Path $env:LOCALAPPDATA 'plaud-tray'

$TaskNames = @(
    'PlaudMeetingsDigest_Lunch',
    'PlaudMeetingsDigest_EOD',
    'PlaudMeetingsDigest_Rollup',
    'PlaudMeetingsDigest_AutoUpdate',   # deprecated - should NOT exist on a current build
    'PlaudMeetingsDigest_Friday',       # legacy
    'PlaudMeetingsDigest_Weekly'        # legacy
)

$Stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$Host_   = $env:COMPUTERNAME
$lines   = New-Object System.Collections.Generic.List[string]
function Add-Line($t = '') { $lines.Add([string]$t) }

# ---- Helpers ---------------------------------------------------------------
function Read-TextNoBom([string]$path) {
    if (-not (Test-Path $path)) { return $null }
    try {
        $t = [System.IO.File]::ReadAllText($path)
        return $t.TrimStart([char]0xFEFF)
    } catch { return $null }
}

# Recursively blank secret values in a parsed-JSON object, in place.
# Redacts: any property whose NAME looks like a secret, AND every leaf value
# under a "checks" subtree (Healthchecks ping IDs are write-capable URLs).
$SecretKeyRe = '(?i)(token|secret|password|api[_-]?key|webhook|ping_base|access|bearer|client_secret)'
function Redact-Node($node, [bool]$force) {
    if ($null -eq $node) { return }
    if ($node -is [System.Management.Automation.PSCustomObject]) {
        foreach ($p in $node.PSObject.Properties) {
            $isSecret   = $p.Name -match $SecretKeyRe
            # Propagate force down ANY secret-named OR 'checks' subtree, so a
            # secret whose value is a nested object/array can't slip through.
            $childForce = $force -or ($p.Name -match '(?i)^checks$') -or $isSecret
            if ($p.Value -is [string]) {
                if (($force -or $isSecret) -and $p.Value) {
                    $p.Value = "<redacted:$($p.Value.Length)chars>"
                }
            } elseif ($p.Value -is [System.Management.Automation.PSCustomObject] -or $p.Value -is [System.Object[]]) {
                Redact-Node $p.Value $childForce
            }
        }
    } elseif ($node -is [System.Object[]]) {
        foreach ($item in $node) { Redact-Node $item $force }
    }
}

# Hash + stamp every script file in a directory. Returns objects for the manifest.
function Get-FileManifest([string]$dir, [string]$label) {
    $out = @()
    if (-not (Test-Path $dir)) { return $out }
    $files = Get-ChildItem -Path (Join-Path $dir '*') -Recurse -File -Include *.ps1,*.py,*.sh,*.json,*.txt -ErrorAction SilentlyContinue |
             Where-Object { $_.FullName -notmatch '__pycache__' }
    foreach ($f in $files) {
        $hash = ''
        try { $hash = (Get-FileHash -Path $f.FullName -Algorithm SHA256 -ErrorAction Stop).Hash } catch { $hash = 'ERR' }
        $rel = $f.FullName.Substring($dir.Length).TrimStart('\')
        $out += [PSCustomObject]@{
            Area = $label; Rel = $rel; SHA256 = $hash
            Bytes = $f.Length; Modified = $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
        }
    }
    return $out
}

# ============================================================================
# Build the report
# ============================================================================
Add-Line "================================================================"
Add-Line " PLAUD-MEETINGS-DIGEST - FIELD BUILD REPORT"
Add-Line " Machine : $Host_"
Add-Line " Captured: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
Add-Line " User    : $env:USERNAME"
Add-Line " PSVersion: $($PSVersionTable.PSVersion)"
Add-Line "================================================================"
Add-Line ""

# ---- 1. Version ------------------------------------------------------------
$ver = Read-TextNoBom $VersionFile
Add-Line "## VERSION"
if ($ver) { Add-Line "  version.txt: $($ver.Trim())" } else { Add-Line "  version.txt: [MISSING] ($VersionFile)" }
Add-Line "  bundle prefix exists: $(Test-Path $BundlePrefix)  ($BundlePrefix)"
Add-Line "  skill dir exists    : $(Test-Path $SkillDir)  ($SkillDir)"
Add-Line "  tray prefix exists  : $(Test-Path $TrayPrefix)  ($TrayPrefix)"
Add-Line ""

# ---- 2. Scheduler health (the highest-value signal) ------------------------
Add-Line "## SCHEDULED TASKS"
foreach ($tn in $TaskNames) {
    $t = Get-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue
    if (-not $t) { Add-Line ("  {0,-34} : [absent]" -f $tn); continue }
    $info = $null
    try { $info = Get-ScheduledTaskInfo -TaskName $tn -ErrorAction SilentlyContinue } catch {}
    $state  = $t.State
    $last   = if ($info) { $info.LastRunTime } else { '?' }
    $result = if ($info) { ('0x{0:X8}' -f $info.LastTaskResult) } else { '?' }
    $next   = if ($info) { $info.NextRunTime } else { '?' }
    Add-Line ("  {0,-34} : state={1} last={2} result={3} next={4}" -f $tn, $state, $last, $result, $next)
}
Add-Line "  (note: PlaudMeetingsDigest_AutoUpdate/_Friday/_Weekly should read [absent] on a current build)"
Add-Line "  (note: if these read [absent] but the install looks fine, re-run this report in an ELEVATED"
Add-Line "         PowerShell - a standard user only sees tasks registered under their own account)"
Add-Line ""

# ---- 3. File manifest (hashes for diffing against canonical) ---------------
$manifest = @()
$manifest += Get-FileManifest $SkillScripts  'skill/scripts'
$manifest += Get-FileManifest $BundleScripts 'bundle/scripts'
Add-Line "## BUILD FILE MANIFEST (SHA256 - diff these against the v2.5.0 tag)"
if ($manifest.Count -eq 0) {
    Add-Line "  [no script files found in either location]"
} else {
    foreach ($m in ($manifest | Sort-Object Area, Rel)) {
        Add-Line ("  [{0,-14}] {1,-28} {2}  {3}b  {4}" -f $m.Area, $m.Rel, $m.SHA256.Substring(0,[Math]::Min(16,$m.SHA256.Length)), $m.Bytes, $m.Modified)
    }
}
Add-Line ""

# ---- 4. Config (REDACTED) --------------------------------------------------
Add-Line "## CONFIG (secrets redacted)"
$redactedJson = $null
$rawConfig = Read-TextNoBom $ConfigPath
if (-not $rawConfig) {
    Add-Line "  [MISSING] $ConfigPath"
} else {
    try {
        $cfg = $rawConfig | ConvertFrom-Json
        Redact-Node $cfg $false
        $redactedJson = $cfg | ConvertTo-Json -Depth 12
        foreach ($l in ($redactedJson -split "`n")) { Add-Line "  $l" }
    } catch {
        Add-Line "  [config present but failed to parse as JSON - possible BOM/encoding issue]: $($_.Exception.Message)"
    }
}
Add-Line ""

# ---- 5. Recent log tail ----------------------------------------------------
Add-Line "## RECENT LOG (last 30 lines)"
$mainLog = Join-Path $LogDir 'plaud-meetings-digest.log'
if (Test-Path $mainLog) {
    $tail = Get-Content $mainLog -Tail 30 -ErrorAction SilentlyContinue
    foreach ($l in $tail) { Add-Line "  $l" }
} else {
    Add-Line "  [no log at $mainLog]"
}
Add-Line ""
Add-Line "================================================================"
Add-Line " END REPORT"
Add-Line "================================================================"

# ============================================================================
# Emit: console (paste-able) + zip (real build files for diffing)
# ============================================================================
$summary = ($lines -join "`r`n")
Write-Host $summary

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$stage = Join-Path $env:TEMP "plaud-build-report-$Stamp"
$buildDir = Join-Path $stage 'build'
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

# Real build files (CODE only - no secrets in scripts). Copy both copies.
foreach ($pair in @(@{src=$SkillScripts; dst='skill-scripts'}, @{src=$BundleScripts; dst='bundle-scripts'})) {
    if (Test-Path $pair.src) {
        $d = Join-Path $buildDir $pair.dst
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Copy-Item -Path (Join-Path $pair.src '*') -Destination $d -Recurse -Force -ErrorAction SilentlyContinue
        # Drop __pycache__ from the copy
        Get-ChildItem -Path $d -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}
if ($ver) { [System.IO.File]::WriteAllText((Join-Path $buildDir 'version.txt'), $ver, (New-Object System.Text.UTF8Encoding $false)) }

# REDACTED config only - never the live config.json
if ($redactedJson) { [System.IO.File]::WriteAllText((Join-Path $stage 'config.redacted.json'), $redactedJson, (New-Object System.Text.UTF8Encoding $false)) }

# Scheduler dump
try { schtasks /query /v /fo LIST 2>$null | Select-String -Pattern 'Plaud' -Context 0,12 | Out-File (Join-Path $stage 'schtasks.txt') -Encoding UTF8 } catch {}

# Log tail (longer than the console summary)
if (Test-Path $mainLog) { Get-Content $mainLog -Tail 200 -ErrorAction SilentlyContinue | Out-File (Join-Path $stage 'log-tail.txt') -Encoding UTF8 }

# Manifest + summary
$manifest | Sort-Object Area, Rel | Format-Table -AutoSize | Out-String | Out-File (Join-Path $stage 'MANIFEST.txt') -Encoding UTF8
[System.IO.File]::WriteAllText((Join-Path $stage 'SUMMARY.txt'), $summary, (New-Object System.Text.UTF8Encoding $false))

$zip = Join-Path $OutDir "plaud-build-report-$Host_-$Stamp.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
try {
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "[OK] Build report written to:" -ForegroundColor Green
    Write-Host "     $zip"
    Write-Host ""
    Write-Host "Send that zip to your Gallant operator (or paste the SUMMARY block above into chat)."
    Write-Host "It contains the actual build files + a REDACTED config (no secrets)."
} catch {
    Write-Host ""
    Write-Host "[!] Could not create zip ($($_.Exception.Message)). Staging dir left at: $stage" -ForegroundColor Yellow
}
