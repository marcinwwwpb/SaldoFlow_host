param(
    [switch]$RemoveVolumes
)
$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir
if (docker inspect saldoflow-oracle 2>$null) {
    if ($RemoveVolumes) {
        docker compose -f compose.oracle.yml down -v
    }
    else {
        docker stop saldoflow-oracle | Out-Null
        Write-Host '[OK] Zatrzymano Oracle.' -ForegroundColor Green
    }
}
else {
    Write-Host '[INFO] Kontener saldoflow-oracle nie istnieje.' -ForegroundColor Yellow
}
