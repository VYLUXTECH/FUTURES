# Wipes C:\futures-bot, downloads latest setup-vps.ps1, and runs it
# Run in PowerShell as Administrator
Remove-Item -Recurse -Force "C:\futures-bot" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Remove-Item "$env:TEMP\setup.ps1" -Force -ErrorAction SilentlyContinue
$wc = New-Object System.Net.WebClient
$wc.Headers.Add("Cache-Control", "no-cache")
$wc.DownloadFile("https://raw.githubusercontent.com/VYLUXTECHINC/FUTURES/bbec3c7/scripts/setup-vps.ps1", "$env:TEMP\setup.ps1")
& "$env:TEMP\setup.ps1"
