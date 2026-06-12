Write-Host "=== Pulling latest changes ===" -ForegroundColor Yellow
cd C:\futures
git remote set-url origin https://github.com/VYLUXTECH/FUTURES.git 2>$null
git pull

Write-Host "`n=== Building frontend ===" -ForegroundColor Yellow
cd C:\futures\web-app
npm install
npm run build

Write-Host "`n=== Restarting bot ===" -ForegroundColor Yellow
C:\nssm\nssm.exe restart FuturesBot

Write-Host "`n=== Restarting tunnel ===" -ForegroundColor Yellow
C:\nssm\nssm.exe restart CloudflaredTunnel

Write-Host "`n=== Done! ===" -ForegroundColor Green
