$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$logsDir = Join-Path $projectRoot "logs"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$envFile = Join-Path $projectRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if (-not $_ -or $_.Trim().StartsWith("#") -or -not $_.Contains("=")) { return }
        $name, $value = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim().Trim('"').Trim("'"), "Process")
    }
}

$hostValue = if ($env:API_HOST) { $env:API_HOST } else { "127.0.0.1" }
$portValue = if ($env:API_PORT) { $env:API_PORT } else { "8010" }

& $pythonPath -m uvicorn app.api.main:app --host $hostValue --port $portValue
