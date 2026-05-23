# Run this in PowerShell as Administrator to clear cached setup script and re-download
$wc = New-Object System.Net.WebClient; $wc.Headers.Add("Cache-Control", "no-cache"); $wc.DownloadFile("https://raw.githubusercontent.com/VYLUXTECHINC/FUTURES/9a9deae/scripts/setup-vps.ps1", "$env:TEMP\setup.ps1"); & "$env:TEMP\setup.ps1"
