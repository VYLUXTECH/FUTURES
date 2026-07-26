<#
.SYNOPSIS
  THE DISCIPLE - Fresh VPS Setup
.DESCRIPTION
  Run as Administrator in PowerShell on a new VPS.
#>

$ErrorActionPreference = "Stop"
$ROOT = "C:\thedisciple"
$FRONTEND = "C:\thedisciple-frontend"

Write-Host "=== THE DISCIPLE Fresh Setup ===" -ForegroundColor Cyan
Write-Host ""

# Admin check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Host "Run as Administrator!" -ForegroundColor Red; exit 1 }

# Python
Write-Host "[1/7] Python..." -ForegroundColor Yellow
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\py.exe"
    Start-Process -Wait "$env:TEMP\py.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
}
python --version

# Git
Write-Host "[2/7] Git..." -ForegroundColor Yellow
if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    $url = "https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/Git-2.45.0-64-bit.exe"
    Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\git.exe"
    Start-Process -Wait "$env:TEMP\git.exe" -ArgumentList "/VERYSILENT /NORESTART /SP- /COMPONENTS='icons,ext,reg,assoc'"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
}
Write-Host "  Git OK" -ForegroundColor Green

# Node.js
Write-Host "[3/7] Node.js..." -ForegroundColor Yellow
if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) {
    $url = "https://nodejs.org/dist/v20.15.1/node-v20.15.1-x64.msi"
    Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\node.msi"
    Start-Process "msiexec.exe" -ArgumentList "/i `"$env:TEMP\node.msi`" /quiet" -Wait
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
}
Write-Host "  Node OK" -ForegroundColor Green

# Clone backend
Write-Host "[4/7] Cloning backend..." -ForegroundColor Yellow
try { taskkill /F /IM python.exe 2>&1 | Out-Null } catch {}
Start-Sleep 2
if (Test-Path $ROOT) { Remove-Item -Recurse -Force $ROOT -ErrorAction SilentlyContinue }
git clone https://github.com/VYLUXTECH/THE-DISCIPLE.git $ROOT

# Clone frontend
Write-Host "[5/7] Cloning frontend..." -ForegroundColor Yellow
if (Test-Path $FRONTEND) { Remove-Item -Recurse -Force $FRONTEND -ErrorAction SilentlyContinue }
git clone https://github.com/VYLUXTECH/futures-frontend.git $FRONTEND

# Install deps
Write-Host "[6/7] Installing deps..." -ForegroundColor Yellow
pip install -r "$ROOT\requirements.txt"
pip install bcrypt
Set-Location $FRONTEND
npm install
npm run build

# Generate secrets and .env
Write-Host "[7/7] Creating .env..." -ForegroundColor Yellow
Set-Location $ROOT
$encKey = python -c "from cryptography.fernet import Fernet; import base64; print(base64.urlsafe_b64encode(Fernet.generate_key()).decode())"
$jwtSecret = python -c "import secrets; print(secrets.token_urlsafe(64))"

Write-Host ""
Write-Host "Enter your PostgreSQL connection string:" -ForegroundColor White
$dbUri = Read-Host "SUPABASE_DB_URI"
Write-Host "Enter Supabase URL (for data):" -ForegroundColor White
$supUrl = Read-Host "SUPABASE_URL"
Write-Host "Enter Supabase service role key:" -ForegroundColor White
$supKey = Read-Host "SUPABASE_KEY"

@"
API_HOST=127.0.0.1
API_PORT=8000
ALLOWED_ORIGINS=https://bot.futuretraders.net
SUPABASE_DB_URI=$dbUri
SUPABASE_URL=$supUrl
SUPABASE_KEY=$supKey
ENCRYPTION_KEY=$encKey
JWT_SECRET=$jwtSecret
AI_BASE_URL=https://api.nexray.eu.cc/ai/gemini
AI_MODEL=gemini
LOG_LEVEL=INFO
"@ | Out-File -FilePath "$ROOT\.env" -Encoding ascii

# Create admin user
Write-Host "Creating admin user..." -ForegroundColor Yellow
python -c @"
from brain.db.postgres import init_db
from backend.auth.password import hash_password
from backend.auth.db import create_user, get_user_by_email
init_db()
if not get_user_by_email('ssegawarichie72@gmail.com'):
    u = create_user('ssegawarichie72@gmail.com', hash_password('#RichieRich206'), 'Richie')
    print('User created:', u['id'] if u else 'FAILED')
else:
    print('User already exists')
"@

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
Write-Host "URL:      https://bot.futuretraders.net" -ForegroundColor White
Write-Host "Email:    ssegawarichie72@gmail.com" -ForegroundColor White
Write-Host "Password: #RichieRich206" -ForegroundColor White
Write-Host ""
Write-Host "Next: Set up Cloudflare tunnel to point to localhost:8000" -ForegroundColor Yellow
Write-Host "Then: nssm install TheDisciple python backend/main.py" -ForegroundColor Yellow
Write-Host "      nssm start TheDisciple" -ForegroundColor Yellow
