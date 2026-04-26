$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

$envFile = Join-Path $projectRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if (-not $_ -or $_.Trim().StartsWith("#") -or -not $_.Contains("=")) { return }
        $name, $value = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim().Trim('"').Trim("'"), "Process")
    }
}

$portValue = if ($env:STREAMLIT_PORT) { $env:STREAMLIT_PORT } else { "8510" }
$addressValue = if ($env:STREAMLIT_HOST) { $env:STREAMLIT_HOST } else { "127.0.0.1" }

& $pythonPath -m streamlit run frontend/streamlit_app.py --server.port $portValue --server.address $addressValue
