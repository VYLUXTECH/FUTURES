<#
.SYNOPSIS
  FUTURES Trading Bot — One-Click VPS Setup
.DESCRIPTION
  Automates: Python, dependencies, .env, Cloudflare Tunnel, services, and startup.
  Run this on a fresh Windows VPS as Administrator.
#>

$ErrorActionPreference = "Stop"
$ROOT = "C:\futures-bot"
$REPO = "https://github.com/VYLUXTECHINC/FUTURES.git"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   FUTURES Trading Bot — VPS Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─── Prerequisites check ──────────────────────────────────
Write-Host "[1/8] Checking prerequisites..." -ForegroundColor Yellow

# Admin check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Run this script as Administrator!" -ForegroundColor Red
    exit 1
}

# Python check
$py = (Get-Command "python" -ErrorAction SilentlyContinue)
if (-not $py) {
    Write-Host "  Python not found. Downloading Python 3.11..." -ForegroundColor Yellow
    $url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $installer = "$env:TEMP\python-3.11.9-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer
    Start-Process -Wait -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
    Write-Host "  Python 3.11 installed." -ForegroundColor Green
} else {
    $ver = python --version 2>&1
    Write-Host "  $ver" -ForegroundColor Green
}

# Git check
$git = (Get-Command "git" -ErrorAction SilentlyContinue)
if (-not $git) {
    Write-Host "  Git not found. Downloading Git..." -ForegroundColor Yellow
    $url = "https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/Git-2.45.0-64-bit.exe"
    $installer = "$env:TEMP\Git-2.45.0-64-bit.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer
    Start-Process -Wait -FilePath $installer -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS=`"icons,ext,reg,assoc`""
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
    Write-Host "  Git installed." -ForegroundColor Green
} else {
    Write-Host "  Git found." -ForegroundColor Green
}

# ─── Clone repo ───────────────────────────────────────────
Write-Host ""
Write-Host "[2/8] Cloning repository..." -ForegroundColor Yellow
if (Test-Path $ROOT) {
    Write-Host "  Directory exists. Pulling latest..." -ForegroundColor Yellow
    Set-Location $ROOT
    git pull
} else {
    git clone $REPO $ROOT
    Write-Host "  Cloned to $ROOT" -ForegroundColor Green
}
Set-Location $ROOT

# ─── Install Python deps ──────────────────────────────────
Write-Host ""
Write-Host "[3/8] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
Write-Host "  Dependencies installed." -ForegroundColor Green

# ─── Generate encryption key ──────────────────────────────
Write-Host ""
Write-Host "[4/8] Generating encryption key..." -ForegroundColor Yellow
$encKey = python -c "from cryptography.fernet import Fernet; import base64; print(base64.urlsafe_b64encode(Fernet.generate_key()).decode())"
Write-Host "  Encryption key generated." -ForegroundColor Green

# ─── Create .env ──────────────────────────────────────────
Write-Host ""
Write-Host "[5/8] Creating .env file..." -ForegroundColor Yellow

$envVars = @{
    "API_HOST" = "127.0.0.1"
    "API_PORT" = "8000"
    "ALLOWED_ORIGINS" = "https://bot.futuretraders.net"
    "SUPABASE_URL" = ""
    "SUPABASE_KEY" = ""
    "SUPABASE_DB_URI" = ""
    "SUPABASE_SERVICE_ROLE_KEY" = ""
    "SUPABASE_JWT_SECRET" = ""
    "ENCRYPTION_KEY" = $encKey
    "AI_BASE_URL" = "https://all-in-1-ais.officialhectormanuel.workers.dev"
    "AI_MODEL" = "deepseek"
    "LOG_LEVEL" = "INFO"
    "TELEGRAM_ADMIN_BOT_TOKEN" = ""
    "TELEGRAM_ADMIN_ID_1" = ""
    "TELEGRAM_ADMIN_ID_2" = ""
}

Write-Host "  Enter your Supabase and Telegram credentials (press Enter to skip optional fields):" -ForegroundColor White
foreach ($key in $envVars.Keys) {
    if ($envVars[$key] -ne "") { continue }
    $val = Read-Host "  $key"
    $envVars[$key] = $val
}

$lines = @()
$lines.Add("# ============================================================")
$lines.Add("# FUTURES – Production Environment Variables")
$lines.Add("# ============================================================")
$lines.Add("")
$lines.Add("# --- API Server ---")
$lines.Add("API_HOST=127.0.0.1")
$lines.Add("API_PORT=8000")
$lines.Add("")
$lines.Add("# --- Allowed Origins ---")
$lines.Add("ALLOWED_ORIGINS=https://bot.futuretraders.net")
$lines.Add("")
$lines.Add("# --- Supabase ---")
$lines.Add("SUPABASE_URL=$($envVars['SUPABASE_URL'])")
$lines.Add("SUPABASE_KEY=$($envVars['SUPABASE_KEY'])")
$lines.Add("SUPABASE_DB_URI=$($envVars['SUPABASE_DB_URI'])")
$lines.Add("SUPABASE_SERVICE_ROLE_KEY=$($envVars['SUPABASE_SERVICE_ROLE_KEY'])")
$lines.Add("SUPABASE_JWT_SECRET=$($envVars['SUPABASE_JWT_SECRET'])")
$lines.Add("")
$lines.Add("# --- Encryption ---")
$lines.Add("ENCRYPTION_KEY=$encKey")
$lines.Add("")
$lines.Add("# --- AI Copilot ---")
$lines.Add("AI_BASE_URL=$($envVars['AI_BASE_URL'])")
$lines.Add("AI_MODEL=$($envVars['AI_MODEL'])")
$lines.Add("")
$lines.Add("# --- Logging ---")
$lines.Add("LOG_LEVEL=INFO")
$lines.Add("")
$lines.Add("# --- Telegram Admin Bot ---")
$lines.Add("TELEGRAM_ADMIN_BOT_TOKEN=$($envVars['TELEGRAM_ADMIN_BOT_TOKEN'])")
$lines.Add("TELEGRAM_ADMIN_ID_1=$($envVars['TELEGRAM_ADMIN_ID_1'])")
$lines.Add("TELEGRAM_ADMIN_ID_2=$($envVars['TELEGRAM_ADMIN_ID_2'])")

$lines -join "`r`n" | Out-File -FilePath "$ROOT\.env" -Encoding ascii
Write-Host "  .env created at $ROOT\.env" -ForegroundColor Green

# ─── Install & configure Cloudflare Tunnel ────────────────
Write-Host ""
Write-Host "[6/8] Setting up Cloudflare Tunnel..." -ForegroundColor Yellow

$cfDir = "C:\cloudflared"
if (-not (Test-Path "$cfDir\cloudflared.exe")) {
    Write-Host "  Downloading cloudflared..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $cfDir | Out-Null
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile "$cfDir\cloudflared.exe"
    Write-Host "  cloudflared downloaded." -ForegroundColor Green
}

$env:Path += ";$cfDir"

Write-Host "  Starting authentication..." -ForegroundColor Yellow
Write-Host "  A browser will open. Log in to Cloudflare and authorize." -ForegroundColor Cyan
Write-Host "  Press Enter after you've completed the authentication..." -ForegroundColor White
$null = Read-Host
cloudflared tunnel login | Out-String | Write-Host

# Create tunnel
$tunnelName = "futures-bot"
Write-Host "  Creating tunnel '$tunnelName'..." -ForegroundColor Yellow
$tunnelResult = cloudflared tunnel create $tunnelName 2>&1 | Out-String
Write-Host $tunnelResult

# Extract tunnel ID
$tunnelId = ""
if ($tunnelResult -match "Created tunnel\s+\S+\s+with id\s+(\S+)") {
    $tunnelId = $matches[1]
} elseif ($tunnelResult -match "Tunnel 'futures-bot' already exists and has id\s+(\S+)") {
    $tunnelId = $matches[1]
}

if (-not $tunnelId) {
    Write-Host "  ERROR: Could not find tunnel ID. Check cloudflared output above." -ForegroundColor Red
    Write-Host "  You'll need to configure DNS routing manually after setup." -ForegroundColor Yellow
}

# Write config.yml
$credFile = "$env:USERPROFILE\.cloudflared\$tunnelId.json"
$configYml = @"
tunnel: $tunnelId
credentials-file: $credFile

ingress:
  - hostname: bot.futuretraders.net
    service: http://localhost:8000
  - service: http_status:404
"@
$configYml | Out-File -FilePath "$cfDir\config.yml" -Encoding ascii
Write-Host "  Config written to $cfDir\config.yml" -ForegroundColor Green

# Route DNS
if ($tunnelId) {
    Write-Host "  Routing bot.futuretraders.net to tunnel..." -ForegroundColor Yellow
    cloudflared tunnel route dns $tunnelName bot.futuretraders.net 2>&1 | Out-String | Write-Host
}

# Install as Windows service
Write-Host "  Installing tunnel as Windows service..." -ForegroundColor Yellow
cloudflared service install 2>&1 | Out-String | Write-Host
Write-Host "  Cloudflare Tunnel configured." -ForegroundColor Green

# ─── Install NSSM + register bot as service ──────────────
Write-Host ""
Write-Host "[7/8] Registering bot as Windows service..." -ForegroundColor Yellow

$nssmDir = "C:\nssm"
if (-not (Test-Path "$nssmDir\nssm.exe")) {
    Write-Host "  Downloading NSSM..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $nssmDir | Out-Null
    $url = "https://nssm.cc/release/nssm-2.24.zip"
    $zip = "$env:TEMP\nssm.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "$env:TEMP\nssm" -Force
    Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" "$nssmDir\nssm.exe"
    Remove-Item -Recurse -Force "$env:TEMP\nssm" -ErrorAction SilentlyContinue
    Remove-Item $zip -ErrorAction SilentlyContinue
}

$pyPath = (Get-Command python).Source

& "$nssmDir\nssm.exe" install FuturesBot @"
$pyPath
"@
& "$nssmDir\nssm.exe" set FuturesBot AppParameters "backend/main.py"
& "$nssmDir\nssm.exe" set FuturesBot AppDirectory "$ROOT"
& "$nssmDir\nssm.exe" set FuturesBot DisplayName "FUTURES Trading Bot"
& "$nssmDir\nssm.exe" set FuturesBot Description "AI-Powered Forex Trading Bot"
& "$nssmDir\nssm.exe" set FuturesBot Start SERVICE_AUTO_START

Write-Host "  Bot service registered." -ForegroundColor Green

# ─── Start everything ─────────────────────────────────────
Write-Host ""
Write-Host "[8/8] Starting services..." -ForegroundColor Yellow

& "$nssmDir\nssm.exe" start FuturesBot
net start cloudflared 2>$null

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SETUP COMPLETE!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Your bot is running at:" -ForegroundColor White
Write-Host "  https://bot.futuretraders.net" -ForegroundColor Green
Write-Host ""
Write-Host "  Service management:" -ForegroundColor White
Write-Host "  nssm start/stop/restart FuturesBot" -ForegroundColor Yellow
Write-Host "  net start/stop cloudflared" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To view bot logs:" -ForegroundColor White
Write-Host "  nssm edit FuturesBot → I/O tab" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Credits:" -ForegroundColor Magenta
Write-Host "  VYLUX TECH — Development & Architecture" -ForegroundColor Magenta
Write-Host "  RICHIE RICH — Concept & Vision" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Cyan
