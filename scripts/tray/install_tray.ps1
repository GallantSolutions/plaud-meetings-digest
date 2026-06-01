# install_tray.ps1 - Install/uninstall the Plaud tray widget on Windows.
#
# Installs three Python deps (pywebview, pystray, watchdog + Pillow), copies
# the tray code into the client's plaud install location, and creates a
# Startup shortcut so the tray launches at login with pythonw.exe (no
# console window).
#
# Designed to be invoked from install.ps1 v2.4.0+ as a sub-step. Can also
# be run standalone for upgrades:
#   .\install_tray.ps1                              # install
#   .\install_tray.ps1 -Uninstall                   # remove autostart + state
#
# Idempotent: re-running re-installs cleanly without duplicating Startup
# shortcuts.

[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) {
    if (-not $Quiet) { Write-Host "[plaud-tray] $msg" -ForegroundColor Cyan }
}

function Write-Warn($msg) {
    Write-Host "[plaud-tray] $msg" -ForegroundColor Yellow
}

# -- Paths ----------------------------------------------------------------

$TrayInstallRoot = Join-Path $env:LOCALAPPDATA 'plaud-tray'
$TrayScriptsDir  = Join-Path $TrayInstallRoot 'scripts'
$StartupDir      = [System.Environment]::GetFolderPath('Startup')
$ShortcutPath    = Join-Path $StartupDir 'Plaud Tray.lnk'
$StateDir        = Join-Path $env:APPDATA 'plaud-tray'

# Source files - relative to this script's location
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# -- Uninstall path -------------------------------------------------------

if ($Uninstall) {
    Write-Step "Uninstalling tray widget..."
    if (Test-Path $ShortcutPath) {
        Remove-Item $ShortcutPath -Force
        Write-Step "Removed Startup shortcut."
    }
    # Stop a running tray process if any
    Get-Process -Name pythonw -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
            if ($cmd -match 'plaud-tray' -or $cmd -match 'scripts.tray.tray') {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                Write-Step "Stopped running tray process (PID $($_.Id))."
            }
        } catch {}
    }
    if (Test-Path $TrayInstallRoot) {
        Remove-Item -Recurse -Force $TrayInstallRoot
        Write-Step "Removed installed tray files at $TrayInstallRoot."
    }
    Write-Step "Done. State file at $StateDir kept (delete manually if desired)."
    exit 0
}

# -- Install path ---------------------------------------------------------

Write-Step "Installing tray widget..."

# 1. Python detection - prefer python.exe in PATH, but check Microsoft Store alias trap
$python = $null
try {
    $cmd = Get-Command python -ErrorAction Stop
    if ($cmd.Source -match 'WindowsApps') {
        Write-Warn "python is the Microsoft Store stub. Disable in Settings -> Apps -> App execution aliases, or use the python installed by plaud-meetings-digest."
    } else {
        $python = $cmd.Source
    }
} catch {}

# Fall back to py launcher
if (-not $python) {
    try { $python = (Get-Command py -ErrorAction Stop).Source } catch {}
}

if (-not $python) {
    Write-Warn "No python found in PATH. Install Python 3.10+ first (this is shipped with plaud-meetings-digest's install.ps1)."
    exit 1
}

Write-Step "Using python at: $python"

# pythonw.exe is the no-console twin
$pythonExe = $python
$pythonwExe = $python -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonwExe)) {
    # py launcher case - fall back to python.exe with a hidden window flag
    $pythonwExe = $pythonExe
    Write-Warn "pythonw.exe not found alongside $pythonExe. Tray will launch with a hidden console (less clean but functional)."
}

# 2. Install Python deps
# --no-warn-script-location suppresses pip's "script X installed in DIR which is not on PATH"
# warning. With $ErrorActionPreference='Stop' set above, that warning to stderr gets raised
# as a terminating NativeCommandError even though pip itself succeeded - so the install would
# halt mid-step. try/catch + explicit $LASTEXITCODE check is the durable pattern.
Write-Step "Installing Python deps (pywebview, pystray, Pillow, watchdog)..."
try {
    & $pythonExe -m pip install --upgrade --quiet --no-warn-script-location pywebview pystray Pillow watchdog 2>&1 | Out-Null
} catch {
    # Swallow stderr-as-error from pip warnings; pip's actual success/failure is on $LASTEXITCODE
}
if ($LASTEXITCODE -ne 0) {
    Write-Warn "pip install failed (exit $LASTEXITCODE). See output above. Tray install aborted."
    exit 1
}

# 3. Copy tray code into install root
Write-Step "Copying tray files to $TrayInstallRoot..."
if (Test-Path $TrayInstallRoot) {
    Remove-Item -Recurse -Force $TrayInstallRoot
}
New-Item -ItemType Directory -Force -Path $TrayScriptsDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $TrayScriptsDir 'tray') | Out-Null

# Copy tray subpackage (exclude dev artifacts that don't belong on client machines)
$trayExclude = @('preview.html', 'README.md', 'install_tray.ps1', '__pycache__')
$trayDest = Join-Path $TrayScriptsDir 'tray'
Copy-Item -Recurse -Force -Path (Join-Path $SourceDir '*') -Destination $trayDest -Exclude $trayExclude
# -Exclude on Copy-Item only filters the top level - sweep nested __pycache__ too.
Get-ChildItem -Path $trayDest -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Copy sibling scripts the tray imports: onedrive_resolve.py
$ParentScripts = Split-Path -Parent $SourceDir
Copy-Item -Force (Join-Path $ParentScripts 'onedrive_resolve.py') $TrayScriptsDir

# Create scripts/__init__.py
New-Item -ItemType File -Path (Join-Path $TrayScriptsDir '__init__.py') -Force | Out-Null

# 4. Create Startup shortcut
Write-Step "Creating Startup shortcut at $ShortcutPath..."
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut($ShortcutPath)
$lnk.TargetPath = $pythonwExe
$lnk.Arguments  = "-m scripts.tray.tray"
$lnk.WorkingDirectory = $TrayInstallRoot
$lnk.IconLocation = (Join-Path $TrayScriptsDir 'tray\assets\kingsway-logo.png')
$lnk.WindowStyle = 7  # minimized - no flash on launch
$lnk.Description = "Plaud - This week (Kingsway action items)"
$lnk.Save()

# 5. State directory
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# 6. Launch now if not already running
$alreadyRunning = $false
try {
    Get-Process -Name pythonw -ErrorAction SilentlyContinue | ForEach-Object {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        if ($cmd -match 'scripts.tray.tray') { $alreadyRunning = $true }
    }
} catch {}

if (-not $alreadyRunning) {
    Write-Step "Launching tray now..."
    Start-Process -FilePath $pythonwExe -ArgumentList "-m","scripts.tray.tray" -WorkingDirectory $TrayInstallRoot -WindowStyle Hidden
} else {
    Write-Step "Tray already running - skipping launch. Restart Windows or kill the process to load new code."
}

Write-Step "Done."
Write-Step "  Tray code:     $TrayInstallRoot"
Write-Step "  Autostart:     $ShortcutPath"
Write-Step "  State file:    $StateDir\state.json"
Write-Step ""
Write-Step "The tray icon will appear in the Windows system tray (look near the clock)."
Write-Step "Click the icon to open the widget. Right-click for menu."
