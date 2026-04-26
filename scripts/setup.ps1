$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonArgs = @("-3.12")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
    $pythonArgs = @()
} else {
    throw "Python was not found on PATH. Install Python 3.12+ and rerun setup."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pythonCommand @pythonArgs -m venv .venv
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

Write-Host "Environment ready."
Write-Host "Next:"
Write-Host "1. Copy .env.example to .env and add credentials."
Write-Host "2. Run .\scripts\start_all.ps1"
