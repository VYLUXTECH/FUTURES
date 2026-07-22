Write-Host "=== Searching C:\ for log files ===" -ForegroundColor Cyan
$logs = Get-ChildItem -Path "C:\" -Recurse -Filter "*.log" -ErrorAction SilentlyContinue -Depth 6
if (-not $logs) {
    Write-Host "No .log files found up to depth 6. Trying without depth limit..." -ForegroundColor Yellow
    $logs = Get-ChildItem -Path "C:\" -Recurse -Filter "*.log" -ErrorAction SilentlyContinue
}
$logs | Select FullName, LastWriteTime | Sort LastWriteTime -Descending | Format-Table -AutoSize

$recent = $logs | Sort LastWriteTime -Descending | Select -First 1
if ($recent) {
    Write-Host ""
    Write-Host "=== Most recent: $($recent.FullName) ===" -ForegroundColor Green
    Write-Host "Last 40 lines:" -ForegroundColor Yellow
    Get-Content $recent.FullName -Tail 40
} else {
    Write-Host "No .log files found anywhere on C:\" -ForegroundColor Red
}
