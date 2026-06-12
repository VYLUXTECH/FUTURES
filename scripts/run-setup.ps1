# FUTURES Trading Bot — One-Click VPS Setup
# Run this in PowerShell as Administrator
#
# Prerequisites:
#   1. Windows VPS (this one: 158.220.89.163)
#   2. Supabase project created with db.txt schema
#   3. Domain bot.futuretraders.net on Cloudflare
#   4. Your Supabase + Telegram credentials ready
#
# Before running: delete any DNS A record for bot.futuretraders.net

Set-ExecutionPolicy RemoteSigned -Scope Process -Force
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/VYLUXTECH/FUTURES/main/scripts/setup-vps.ps1" -OutFile "$env:TEMP\setup.ps1"
& "$env:TEMP\setup.ps1"
