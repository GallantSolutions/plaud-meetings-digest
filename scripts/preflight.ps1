# ============================================================================
# preflight.ps1 - runs FIRST, refuses install until the environment is sane.
# ============================================================================
# Detection-in-code for the Windows-enterprise landmines that have actually
# broken this bundle in the field (v2.4.1 outage, 2026-05-29). The cure for a
# landmine is a check here, not a line in an operator memory.
#
#   .\preflight.ps1            # check; exit 1 if any hard blocker fails
#   .\preflight.ps1 -Warn      # report only, never exit non-zero (advisory)
#
# Hard blockers (exit 1): no real Python interpreter (only the WindowsApps
# alias). Soft warnings: missing Claude CLI / Git, non-writable OneDrive path,
# old PowerShell. Full enterprise landmine catalogue lives in the Gallant vault
# at 02_research/wiki/topics/windows-enterprise-deployment/.
#
# Strings here are deliberately plain ASCII (no inner quotes, no > or em-dash)
# so PowerShell 5.1 + pwsh 7 both parse them cleanly.
# ============================================================================

#Requires -Version 5.1

param([switch]$Warn)

$ErrorActionPreference = 'Continue'
$script:blockers = @()
$script:warnings = @()

function Say-Ok   { param([string]$T) Write-Host "  [ ok ] $T" -ForegroundColor Green }
function Say-Warn { param([string]$T) Write-Host "  [warn] $T" -ForegroundColor Yellow; $script:warnings += $T }
function Say-Fail { param([string]$T) Write-Host "  [FAIL] $T" -ForegroundColor Red;    $script:blockers += $T }

Write-Host ""
Write-Host "Plaud Meetings Digest - preflight" -ForegroundColor Cyan
Write-Host "==================================="

# ---- 1. Real Python interpreter (Bug 1: WindowsApps alias trap) ----------
# Get-Command python on a stock Windows install resolves to the MS Store App
# Execution Alias, which cannot run under Task Scheduler (exits 0x80070001).
# Resolve a real interpreter: py.exe launcher, then per-user install path,
# then a non-WindowsApps python on PATH. Mirrors schedule.ps1 Resolve-PythonExe.
$realPython = $null
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    try {
        $p = (& py.exe -3 -c "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $p -and (Test-Path $p.Trim())) { $realPython = $p.Trim() }
    } catch {}
}
if (-not $realPython) {
    $programsRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path $programsRoot) {
        $realPython = Get-ChildItem -Path $programsRoot -Filter 'Python3*' -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName 'python.exe' } |
            Where-Object { Test-Path $_ } | Select-Object -First 1
    }
}
$pathPython = (Get-Command python -ErrorAction SilentlyContinue).Source
$pathIsAlias = ($pathPython -like '*WindowsApps*')
if (-not $realPython -and $pathPython -and -not $pathIsAlias) {
    $realPython = $pathPython   # a normal python on PATH is fine
}

if ($realPython) {
    Say-Ok "Python: $realPython"
    if ($pathIsAlias) {
        Say-Warn "PATH python is the WindowsApps alias. schedule.ps1 ignores it and uses the real interpreter, but consider disabling the alias under Settings, App execution aliases."
    }
} elseif ($pathIsAlias) {
    Say-Fail "Only the Microsoft Store python alias is present. It cannot run under Task Scheduler. Install Python from python.org (3.11 or newer), then re-run."
} else {
    Say-Fail "No Python interpreter found. Install Python from python.org (3.11 or newer), then re-run."
}

# ---- 2. PowerShell edition (Bug 7 context: PS 5.1 -Encoding UTF8 BOM) -----
$psv = $PSVersionTable.PSVersion
if ($psv.Major -ge 5) {
    Say-Ok "PowerShell $psv"
    if ($psv.Major -eq 5) {
        Say-Warn "Windows PowerShell 5.1: the installer writes config.json BOM-less via .NET (handled in code). Do not hand-edit config.json with Set-Content -Encoding UTF8 (it adds a BOM that breaks the runner)."
    }
} else {
    Say-Fail "PowerShell $psv is too old. Need 5.1 or newer."
}

# ---- 3. Claude CLI (the runner shells out to it) -------------------------
if (Get-Command claude -ErrorAction SilentlyContinue) {
    Say-Ok "Claude CLI present"
} else {
    Say-Warn "Claude CLI (claude) not on PATH. The digest runner needs it. Install per OPERATOR-INSTALL-GUIDE before scheduled runs will produce output."
}

# ---- 4. Git (used by some update/install paths) --------------------------
if (Get-Command git -ErrorAction SilentlyContinue) {
    Say-Ok "Git present"
} else {
    Say-Warn "Git not found. Some install/update paths use it. Install from git-scm.com if a step needs it."
}

# ---- 5. OneDrive destination writable -------------------------------------
$oneDrive = $env:OneDrive
if (-not $oneDrive) { $oneDrive = $env:OneDriveCommercial }
if ($oneDrive -and (Test-Path $oneDrive)) {
    try {
        $probe = Join-Path $oneDrive ('.gallant-preflight-' + [System.IO.Path]::GetRandomFileName())
        [System.IO.File]::WriteAllText($probe, 'ok'); Remove-Item $probe -Force
        Say-Ok "OneDrive writable: $oneDrive"
    } catch {
        Say-Warn "OneDrive folder present but not writable at $oneDrive"
    }
} else {
    Say-Warn "OneDrive path not detected. Confirm the destination folder exists before install."
}

# ---- 6. Execution policy --------------------------------------------------
$ep = Get-ExecutionPolicy
if ($ep -in @('Restricted','AllSigned')) {
    Say-Warn "ExecutionPolicy is $ep. Scheduled tasks invoke powershell with -ExecutionPolicy Bypass so they are unaffected, but interactive runs may be blocked. Consider RemoteSigned for CurrentUser."
} else {
    Say-Ok "ExecutionPolicy: $ep"
}

# ---- Summary --------------------------------------------------------------
Write-Host ""
if ($script:blockers.Count -gt 0) {
    Write-Host "Preflight FAILED - $($script:blockers.Count) blocker(s):" -ForegroundColor Red
    $script:blockers | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    if ($Warn) {
        Write-Host "(-Warn set: not exiting non-zero, but install will likely fail until these are fixed.)" -ForegroundColor Yellow
        exit 0
    }
    exit 1
}
if ($script:warnings.Count -gt 0) {
    Write-Host "Preflight passed with $($script:warnings.Count) warning(s) - review above." -ForegroundColor Yellow
} else {
    Write-Host "Preflight clean." -ForegroundColor Green
}
exit 0
