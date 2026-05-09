# Service Launcher — Windows Installer
# Creates a Task Scheduler task so the app starts automatically at login.
#
# Usage (run from PowerShell as the current user, NOT as Administrator):
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Port 8080

param(
    [switch]$Uninstall,
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"

# ─── Paths ───────────────────────────────────────────────────────────────────
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir     = Join-Path $ScriptRoot "v3"
$VenvDir    = Join-Path $env:USERPROFILE ".venvs\main"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir "Scripts\pip.exe"
$AppScript  = Join-Path $AppDir "app.py"
$ConfigFile = Join-Path $AppDir "scripts_config.yaml"
$ExampleFile= Join-Path $AppDir "scripts_config.yaml.example"
$TaskName   = "ServiceLauncher"
$StartBat   = Join-Path $ScriptRoot "start.bat"

# ─── Helpers ─────────────────────────────────────────────────────────────────
function Write-Info    { param($msg) Write-Host "-> $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host ":check: $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "!! $msg" -ForegroundColor Yellow }
function Write-Err     { param($msg) Write-Host "ERROR: $msg" -ForegroundColor Red }
function Write-Header  { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor White }
function Write-Banner  { param($msg) Write-Host $msg -ForegroundColor White }

# ─── Uninstall ───────────────────────────────────────────────────────────────
if ($Uninstall) {
    Write-Header "Uninstalling Service Launcher"

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Info "Stopping task..."
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Write-Info "Removing scheduled task..."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Success "Scheduled task '$TaskName' removed"
    } else {
        Write-Warn "Scheduled task '$TaskName' not found — already uninstalled?"
    }

    # Remove the start.bat if it exists
    if (Test-Path $StartBat) {
        Remove-Item $StartBat
        Write-Success "Removed start.bat"
    }

    # Remove the user env var
    [System.Environment]::SetEnvironmentVariable("SERVICE_LAUNCHER_PORT", $null, "User")

    Write-Host ""
    Write-Success "Uninstall complete. App files in $ScriptRoot were NOT deleted."
    exit 0
}

# ─── Banner ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Banner "Service Launcher — Windows Installer"
Write-Host "========================================"
Write-Host "  User:        $env:USERNAME"
Write-Host "  App dir:     $AppDir"
Write-Host "  Virtual env: $VenvDir"
Write-Host "  Port:        $Port"
Write-Host "========================================"

# ─── Checks ──────────────────────────────────────────────────────────────────
Write-Header "1. Checking requirements"

if (-not (Test-Path $AppDir)) {
    Write-Err "v3\ directory not found at $AppDir"
    Write-Err "Run this script from the service-launcher repository root."
    exit 1
}
Write-Success "App directory found"

# Locate Python 3.8+
$PythonExe = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $raw = & $cmd --version 2>&1
        $verStr = if ($raw -is [string]) { $raw } else { $raw | Out-String }
        if ($verStr -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 8) {
                $PythonExe = (Get-Command $cmd -ErrorAction SilentlyContinue).Source
                if (-not $PythonExe) { $PythonExe = $cmd }
                Write-Success "Python $major.$minor found: $PythonExe"
                break
            }
        }
    } catch { }
}

if (-not $PythonExe) {
    Write-Err "Python 3.8 or higher not found."
    Write-Err "Download and install from: https://www.python.org/downloads/"
    Write-Err "IMPORTANT: Check 'Add Python to PATH' during installation."
    exit 1
}

# ─── Virtual environment ──────────────────────────────────────────────────────
Write-Header "2. Setting up virtual environment"

if (Test-Path $VenvDir) {
    Write-Success "Virtual env already exists at $VenvDir"
} else {
    Write-Info "Creating virtual environment at $VenvDir..."
    $venvParent = Split-Path $VenvDir
    if (-not (Test-Path $venvParent)) {
        New-Item -ItemType Directory -Force -Path $venvParent | Out-Null
    }
    & $PythonExe -m venv $VenvDir
    Write-Success "Virtual environment created"
}

Write-Info "Installing/updating dependencies..."
& $VenvPip install --quiet --upgrade pip
& $VenvPip install --quiet -r (Join-Path $AppDir "requirements.txt")
Write-Success "Dependencies installed"

# ─── Config file ─────────────────────────────────────────────────────────────
Write-Header "3. Configuration"

if (-not (Test-Path $ConfigFile)) {
    if (Test-Path $ExampleFile) {
        Copy-Item $ExampleFile $ConfigFile
        Write-Success "Created scripts_config.yaml from example"
        Write-Warn "Edit $ConfigFile to configure your scripts"
    } else {
        Write-Err "scripts_config.yaml not found and no example file available"
        exit 1
    }
} else {
    Write-Success "scripts_config.yaml already exists"
}

# ─── Task Scheduler ──────────────────────────────────────────────────────────
Write-Header "4. Registering startup task (Task Scheduler)"

# Store port as a user-level environment variable (picked up by app.py)
[System.Environment]::SetEnvironmentVariable("SERVICE_LAUNCHER_PORT", "$Port", "User")
Write-Success "Environment variable SERVICE_LAUNCHER_PORT=$Port set (user-level)"

# Build a wrapper batch file — Task Scheduler runs this so the env var is
# passed in and the window stays hidden using pythonw.
$pythonW = Join-Path $VenvDir "Scripts\pythonw.exe"
# Fall back to python.exe if pythonw is missing (some distros omit it)
if (-not (Test-Path $pythonW)) { $pythonW = $VenvPython }

$wrapperBat = Join-Path $AppDir "_launcher.bat"
@"
@echo off
set SERVICE_LAUNCHER_PORT=$Port
set VIRTUAL_ENV=$VenvDir
set PATH=$VenvDir\Scripts;%PATH%
"$pythonW" "$AppScript"
"@ | Set-Content $wrapperBat -Encoding ASCII
Write-Success "Created launcher wrapper: $wrapperBat"

# Remove any previous registration
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Info "Replaced existing task"
}

$action   = New-ScheduledTaskAction -Execute "cmd.exe" `
              -Argument "/c `"$wrapperBat`"" `
              -WorkingDirectory $AppDir

$trigger  = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -Hidden

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Service Launcher - Web-based script runner on port $Port" `
    -RunLevel Highest | Out-Null

Write-Success "Task '$TaskName' registered (runs at login, hidden)"

# ─── Start ────────────────────────────────────────────────────────────────────
Write-Header "5. Starting service now"

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3

$state = (Get-ScheduledTask -TaskName $TaskName).State
if ($state -eq "Running") {
    Write-Success "Service is running"
} else {
    Write-Warn "Task state: $state"
    Write-Warn "The app may take a few seconds to start."
    Write-Warn "Check logs: $AppDir\script_runner.log"
}

# ─── start.bat shortcut ──────────────────────────────────────────────────────
@"
@echo off
REM Service Launcher — manual start
REM Double-click this file to start the web app.
set SERVICE_LAUNCHER_PORT=$Port
set VIRTUAL_ENV=$VenvDir
set PATH=$VenvDir\Scripts;%PATH%
cd /d "$AppDir"
echo Starting Service Launcher on http://localhost:$Port
echo Close this window to stop the app.
"$VenvPython" "$AppScript"
pause
"@ | Set-Content $StartBat -Encoding ASCII
Write-Success "Created start.bat for manual launch (double-click to run)"

# ─── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Open in your browser:"
Write-Host "  http://localhost:$Port" -ForegroundColor Cyan
Write-Host ""
Write-Host "  The app starts automatically at Windows login."
Write-Host "  For manual start: double-click start.bat"
Write-Host ""
Write-Host "  Manage via Task Scheduler (taskschd.msc):"
Write-Host "    Task name: $TaskName"
Write-Host ""
Write-Host "  View logs: $AppDir\script_runner.log"
Write-Host ""
Write-Host "  To uninstall:"
Write-Host "  powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall"
Write-Host "========================================"
Write-Host ""
