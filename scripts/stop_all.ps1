$ErrorActionPreference = "SilentlyContinue"

$ports = @(8010, 8510)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($connection in $connections) {
        Stop-Process -Id $connection.OwningProcess -Force
        Write-Host "Stopped process $($connection.OwningProcess) on port $port"
    }
}
