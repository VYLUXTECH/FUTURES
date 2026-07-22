# Finds futuresbrain.log and shows last 50 relevant Signal/Pipeline lines
$possible = @(
    ".\brain\logs\futuresbrain.log",
    "..\brain\logs\futuresbrain.log",
    "$env:USERPROFILE\FUTURES-TRADING-BOT\brain\logs\futuresbrain.log",
    "$env:USERPROFILE\FUTURES\brain\logs\futuresbrain.log"
)

$log = $null
foreach ($p in $possible) {
    if (Test-Path $p) { $log = $p; break }
}

if (-not $log) {
    Write-Host "Log file not found. Searching drives..." -ForegroundColor Yellow
    $log = Get-ChildItem -Path C:\ -Recurse -Filter "futuresbrain.log" -ErrorAction SilentlyContinue -Depth 5 | Select-Object -First 1 -ExpandProperty FullName
}

if (-not $log) {
    Write-Host "ERROR: futuresbrain.log not found anywhere." -ForegroundColor Red
    exit 1
}

Write-Host "=== Reading: $log ===" -ForegroundColor Cyan
Write-Host ""

# Extract relevant lines
Select-String -Path $log -Pattern "(SIGNAL|Pipeline error|S1 neutral|S3 ignore|S4 no|Confidence|Alignment blocked|Risk gate|Cooldown|Drawdown|Max daily|Spread|Margin|News window|ATR spike|S8_bias|MT5 init|Trade executed|User cycle error)" | Select-Object -Last 60 | ForEach-Object { $_.Line }
