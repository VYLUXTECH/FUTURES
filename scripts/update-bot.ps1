Write-Host "=== Pulling latest changes ===" -ForegroundColor Yellow
cd C:\thedisciple
git remote set-url origin https://github.com/VYLUXTECH/FUTURES.git 2>$null
git pull

Write-Host "`n=== Installing Python deps ===" -ForegroundColor Yellow
pip install -r requirements.txt
pip install mplfinance

Write-Host "`n=== Building frontend ===" -ForegroundColor Yellow
cd C:\thedisciple-frontend
git pull
npm install
npm run build

Write-Host "`n=== Restarting bot ===" -ForegroundColor Yellow
C:\nssm\nssm.exe restart TheDisciple

Write-Host "`n=== Restarting tunnel ===" -ForegroundColor Yellow
C:\nssm\nssm.exe restart CloudflaredTunnel

Write-Host "`n=== Done! ===" -ForegroundColor Green
