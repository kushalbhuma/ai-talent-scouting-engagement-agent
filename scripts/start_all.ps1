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

$apiHost = if ($env:API_HOST) { $env:API_HOST } else { "127.0.0.1" }
$apiPort = if ($env:API_PORT) { $env:API_PORT } else { "8010" }
$uiHost = if ($env:STREAMLIT_HOST) { $env:STREAMLIT_HOST } else { "127.0.0.1" }
$uiPort = if ($env:STREAMLIT_PORT) { $env:STREAMLIT_PORT } else { "8510" }

$apiOut = Join-Path $logsDir "uvicorn.out.log"
$apiErr = Join-Path $logsDir "uvicorn.err.log"
$uiOut = Join-Path $logsDir "streamlit.out.log"
$uiErr = Join-Path $logsDir "streamlit.err.log"

$api = Start-Process -FilePath $pythonPath `
    -ArgumentList "-m","uvicorn","app.api.main:app","--host",$apiHost,"--port",$apiPort `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $apiOut `
    -RedirectStandardError $apiErr `
    -PassThru

$ui = Start-Process -FilePath $pythonPath `
    -ArgumentList "-m","streamlit","run","frontend/streamlit_app.py","--server.port",$uiPort,"--server.address",$uiHost `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $uiOut `
    -RedirectStandardError $uiErr `
    -PassThru

Write-Host "API PID: $($api.Id) -> http://$apiHost`:$apiPort"
Write-Host "UI PID: $($ui.Id) -> http://$uiHost`:$uiPort"
Write-Host "Logs directory: $logsDir"
