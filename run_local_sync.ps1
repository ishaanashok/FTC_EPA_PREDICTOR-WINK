# FTC Predictor Local Data Sync - PowerShell Wrapper
# Makes it easier to run the Python sync script

param(
    [Parameter(Mandatory=$true)]
    [int]$Season,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("teams", "events", "matches", "all")]
    [string]$Sync,
    
    [switch]$Setup
)

# Set working directory to script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "FTC Predictor Local Data Sync" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

if ($Setup) {
    Write-Host "Running setup..." -ForegroundColor Yellow
    python setup_local_sync.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Setup failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "Setup completed successfully!" -ForegroundColor Green
    Write-Host ""
}

Write-Host "Season: $Season" -ForegroundColor White
Write-Host "Operation: $Sync" -ForegroundColor White
Write-Host ""

Write-Host "Starting sync..." -ForegroundColor Yellow
python local_data_sync.py --season $Season --sync $Sync

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Sync completed successfully!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Sync failed. Check the logs for details." -ForegroundColor Red
    Write-Host "Log file: local_sync.log" -ForegroundColor Yellow
}
