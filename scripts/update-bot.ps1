Write-Host "=== Pulling latest changes ===" -ForegroundColor Yellow
cd C:\futures
git pull
Write-Host "`n=== Restarting bot ===" -ForegroundColor Yellow
C:\nssm\nssm.exe restart FuturesBot
Write-Host "`n=== Restarting tunnel ===" -ForegroundColor Yellow
C:\nssm\nssm.exe restart CloudflaredTunnel
Write-Host "`n=== Done! ===" -ForegroundColor Green
