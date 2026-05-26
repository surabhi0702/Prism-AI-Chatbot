# Stop any process listening on the given port (default 8000)
param([int]$Port = 8000)
$pids = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if (-not $pids) {
    Write-Host "Port $Port is free."
    exit 0
}
foreach ($procId in $pids) {
    Write-Host "Stopping PID $procId on port $Port..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
Write-Host "Done."
