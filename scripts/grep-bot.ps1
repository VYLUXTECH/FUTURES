$log = "C:\futures\brain\logs\futuresbrain.log"
Write-Host "=== Lines from 2026-06-19 ===" -ForegroundColor Cyan
Select-String $log -Pattern "2026-06-19" | Select-Object -First 20 | ForEach-Object { $_.Line }

Write-Host ""
Write-Host "=== Lines with 'brain' or 'futuresbrain' or 'MT5' or 'trading' or 'pipeline' or 'signal' ===" -ForegroundColor Cyan
Select-String $log -Pattern "(brain\.|futuresbrain|MT5|trading|pipeline|signal|SIGNAL|cycle|connect_user|Trade|trade)" | Select-Object -Last 30 | ForEach-Object { $_.Line }

Write-Host ""
Write-Host "=== Total lines ===" -ForegroundColor Cyan
(Get-Content $log).Count
