# KILLS STALE PROCESSES, WIPES C:\futures-bot, THEN RUNS SETUP
# Run in PowerShell as Administrator
taskkill /F /IM python.exe 2>$null
taskkill /F /IM terminal64.exe 2>$null
taskkill /F /IM caddy.exe 2>$null
taskkill /F /IM caddy_windows_amd64.exe 2>$null
Start-Sleep -Seconds 2
Remove-Item -Recurse -Force "C:\futures-bot" -ErrorAction SilentlyContinue
Set-Location C:\
$wc = New-Object System.Net.WebClient
$wc.Headers.Add("Cache-Control", "no-cache")
$wc.DownloadFile("https://raw.githubusercontent.com/VYLUXTECHINC/FUTURES/47a7f53/scripts/setup-vps.ps1", "$env:TEMP\setup.ps1")
& "$env:TEMP\setup.ps1"
