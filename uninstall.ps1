# ============================================================================
# Plaud Meetings Digest — Windows Uninstaller
# ============================================================================
# Removes scheduled tasks, skills, scripts, config, and state. Does NOT
# uninstall Plaud MCP, Claude Code, Node, Python, or python-docx (you may
# use them for other things). Does NOT delete past meeting .docx files in
# your OneDrive folder.
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = 'Continue'

function Write-Ok   { param([string]$Text) Write-Host "✓ $Text" -ForegroundColor Green }
function Write-Warn { param([string]$Text) Write-Host "⚠ $Text" -ForegroundColor Yellow }

Write-Host ""
Write-Host "Plaud Meetings Digest — Uninstaller" -ForegroundColor Cyan
Write-Host ""

# Remove scheduled tasks (current + legacy)
$TaskNames = @(
    'PlaudMeetingsDigest_Lunch',
    'PlaudMeetingsDigest_EOD',
    'PlaudMeetingsDigest_Rollup',
    'PlaudMeetingsDigest_Friday',
    'PlaudMeetingsDigest_Weekly'
)
$AnyRemoved = $false
foreach ($t in $TaskNames) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Ok "Removed task: $t"
        $AnyRemoved = $true
    }
}
if (-not $AnyRemoved) { Write-Warn "No scheduled tasks found" }

# Remove skill dirs
foreach ($d in @(
    (Join-Path $HOME '.claude\skills\meetings-digest'),
    (Join-Path $HOME '.claude\skills\weekly-rollup')
)) {
    if (Test-Path $d) {
        Remove-Item -Path $d -Recurse -Force
        Write-Ok "Removed: $d"
    }
}

# Optionally remove Plaud MCP
Write-Host ""
$removeMcp = Read-Host "Also remove Plaud MCP from Claude Code? [y/N]"
if ($removeMcp -eq 'y') {
    try {
        claude mcp remove plaud 2>$null
        Write-Ok "Plaud MCP removed from Claude Code"
    } catch {
        Write-Warn "Could not remove Plaud MCP automatically. Edit ~/.claude/mcp.json manually if needed."
    }
}

Write-Host ""
Write-Host "✓ Uninstalled." -ForegroundColor Green
Write-Host "Past meeting .docx files left untouched in your OneDrive folder."
Write-Host ""
