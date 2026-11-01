# One-step setup + run for Windows (PowerShell).
#
# Usage (from the project folder):
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#
# What it does: picks a compatible Python, creates .venv, installs
# requirements, checks that numpy/scikit-learn load, then starts the app.
param([switch]$Force)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (($PSScriptRoot -match "OneDrive") -and (-not $Force)) {
    Write-Host ""
    Write-Host "This folder is inside OneDrive. OneDrive sync can corrupt a virtual" -ForegroundColor Yellow
    Write-Host "environment (this causes numpy 'DLL load failed' errors)." -ForegroundColor Yellow
    Write-Host "Move/clone the project to a folder like C:\dev\autonomous-hiring-agent" -ForegroundColor Yellow
    Write-Host "and run this script again. To run here anyway: .\setup.ps1 -Force" -ForegroundColor Yellow
    exit 1
}

function Find-Python {
    foreach ($v in @("3.12", "3.13", "3.11")) {
        try {
            & py "-$v" -c "import sys" 2>$null
            if ($LASTEXITCODE -eq 0) { return @("py", "-$v") }
        } catch { }
    }
    try {
        & python -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) { return @("python") }
    } catch { }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "Python not found. Install Python 3.12 from https://www.python.org/downloads/ and run again." -ForegroundColor Red
    exit 1
}
$pyExe = $py[0]
$pyArgs = @()
if ($py.Count -gt 1) { $pyArgs = $py[1..($py.Count - 1)] }

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# If an existing venv is broken (e.g. numpy DLL error), rebuild it.
if (Test-Path $venvPy) {
    & $venvPy -c "import numpy" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Existing .venv looks broken - recreating it..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force (Join-Path $PSScriptRoot ".venv")
    }
}

if (-not (Test-Path $venvPy)) {
    Write-Host "Creating virtual environment..."
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Could not create .venv" -ForegroundColor Red; exit 1 }
}

Write-Host "Installing dependencies (first run takes a few minutes)..."
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed. If you are on Python 3.14 or newer, install Python 3.12 and run again." -ForegroundColor Red
    exit 1
}

& $venvPy -c "import numpy, sklearn, flask, networkx; print('Dependencies OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Packages installed but failed to load." -ForegroundColor Red
    Write-Host "Install the Microsoft Visual C++ Redistributable (x64):" -ForegroundColor Yellow
    Write-Host "  https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Yellow
    Write-Host "then run this script again." -ForegroundColor Yellow
    exit 1
}

$env:FLASK_ENV = "development"
Write-Host ""
Write-Host "Starting app: open http://127.0.0.1:5000 in your browser (Ctrl+C to stop)" -ForegroundColor Green
& $venvPy app.py
