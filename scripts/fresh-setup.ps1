<#
.SYNOPSIS
  FUTURES Trading Bot - Fresh VPS Setup (No External Auth)
.DESCRIPTION
  Sets up everything from scratch: Python, backend, frontend, Cloudflare Tunnel, services.
  Auth is fully self-hosted (JWT + PostgreSQL). No Supabase auth.
  Run as Administrator on a fresh Windows VPS.
#>

$ErrorActionPreference = "Stop"
$ROOT = "C:\futures"
$FRONTEND = "C:\futures-frontend"
$BACKEND_REPO = "https://github.com/VYLUXTECH/FUTURES.git"
$FRONTEND_REPO = "https://github.com/VYLUXTECH/futures-frontend.git"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FUTURES Bot - Fresh VPS Setup" -ForegroundColor Cyan
Write-Host "  (No External Auth)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---- Admin check ----------------------------------------------------
Write-Host "[1/10] Checking admin..." -ForegroundColor Yellow
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "  ERROR: Run as Administrator!" -ForegroundColor Red
    exit 1
}
Write-Host "  Admin OK." -ForegroundColor Green

# ---- Install Python -------------------------------------------------
Write-Host ""
Write-Host "[2/10] Checking Python..." -ForegroundColor Yellow
$py = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "  Installing Python 3.11..." -ForegroundColor Yellow
    $url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $installer = "$env:TEMP\python-installer.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer
    Start-Process -Wait -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
    Write-Host "  Python installed." -ForegroundColor Green
} else {
    Write-Host "  $(python --version)" -ForegroundColor Green
}

# ---- Install Git ----------------------------------------------------
Write-Host ""
Write-Host "[3/10] Checking Git..." -ForegroundColor Yellow
$git = Get-Command "git" -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Host "  Installing Git..." -ForegroundColor Yellow
    $url = "https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/Git-2.45.0-64-bit.exe"
    $installer = "$env:TEMP\git-installer.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer
    Start-Process -Wait -FilePath $installer -ArgumentList "/VERYSILENT /NORESTART /SP- /CLOSEAPPLICATIONS /COMPONENTS='icons,ext,reg,assoc'"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
    Write-Host "  Git installed." -ForegroundColor Green
} else {
    Write-Host "  Git found." -ForegroundColor Green
}

# ---- Install Node.js (for frontend) ---------------------------------
Write-Host ""
Write-Host "[4/10] Checking Node.js..." -ForegroundColor Yellow
$node = Get-Command "node" -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "  Installing Node.js 20 LTS..." -ForegroundColor Yellow
    $url = "https://nodejs.org/dist/v20.15.1/node-v20.15.1-x64.msi"
    $installer = "$env:TEMP\node-installer.msi"
    Invoke-WebRequest -Uri $url -OutFile $installer
    Start-Process -Wait -FilePath "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
    Write-Host "  Node.js installed." -ForegroundColor Green
} else {
    Write-Host "  $(node --version)" -ForegroundColor Green
}

# ---- Clone backend repo ---------------------------------------------
Write-Host ""
Write-Host "[5/10] Cloning backend..." -ForegroundColor Yellow

try { taskkill /F /IM python.exe 2>&1 | Out-Null } catch {}
try { taskkill /F /IM terminal64.exe 2>&1 | Out-Null } catch {}
Start-Sleep -Seconds 2

if (Test-Path $ROOT) {
    Write-Host "  Removing old backend..." -ForegroundColor Yellow
    $retries = 5
    while ($retries -gt 0 -and (Test-Path $ROOT)) {
        try { Remove-Item -Recurse -Force $ROOT -ErrorAction Stop; break } catch {}
        try { cmd /c "rmdir /S /Q $ROOT 2>nul" } catch {}
        Start-Sleep -Seconds 3
        $retries--
    }
    if (Test-Path $ROOT) {
        Write-Host "  ERROR: Cannot delete $ROOT. Reboot and try again." -ForegroundColor Red
        exit 1
    }
}
git clone $BACKEND_REPO $ROOT
Write-Host "  Backend cloned." -ForegroundColor Green

# ---- Clone frontend repo --------------------------------------------
Write-Host ""
Write-Host "[6/10] Cloning frontend..." -ForegroundColor Yellow

if (Test-Path $FRONTEND) {
    Remove-Item -Recurse -Force $FRONTEND -ErrorAction SilentlyContinue
}
git clone $FRONTEND_REPO $FRONTEND
Write-Host "  Frontend cloned." -ForegroundColor Green

# ---- Install Python deps --------------------------------------------
Write-Host ""
Write-Host "[7/10] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r "$ROOT\requirements.txt"
pip install bcrypt
Write-Host "  Python deps installed." -ForegroundColor Green

# ---- Install frontend deps ------------------------------------------
Write-Host ""
Write-Host "  Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location $FRONTEND
npm install
Write-Host "  Frontend deps installed." -ForegroundColor Green

# ---- Generate secrets -----------------------------------------------
Write-Host ""
Write-Host "[8/10] Generating secrets..." -ForegroundColor Yellow
$encKey = python -c "from cryptography.fernet import Fernet; import base64; print(base64.urlsafe_b64encode(Fernet.generate_key()).decode())"
$jwtSecret = python -c "import secrets; print(secrets.token_urlsafe(64))"
Write-Host "  Secrets generated." -ForegroundColor Green

# ---- Collect credentials --------------------------------------------
Write-Host ""
Write-Host "  Enter your database credentials:" -ForegroundColor White
Write-Host "  (SUPABASE_DB_URI = postgresql://... connection string)" -ForegroundColor DarkGray
Write-Host ""

$dbUri = Read-Host "  SUPABASE_DB_URI"
$supabaseUrl = Read-Host "  SUPABASE_URL (for data operations)"
$supabaseKey = Read-Host "  SUPABASE_KEY (service role key)"

# ---- Write .env -----------------------------------------------------
Write-Host ""
Write-Host "  Writing .env..." -ForegroundColor Yellow

$lines = @(
    "# ============================================================"
    "# FUTURES - Production Environment (Self-Hosted Auth)"
    "# ============================================================"
    ""
    "# --- API Server ---"
    "API_HOST=127.0.0.1"
    "API_PORT=8000"
    ""
    "# --- Allowed Origins ---"
    "ALLOWED_ORIGINS=https://bot.futuretraders.net"
    ""
    "# --- PostgreSQL (Supabase Transaction Pooler or any Postgres) ---"
    "SUPABASE_DB_URI=$dbUri"
    ""
    "# --- Supabase (data operations only, NOT auth) ---"
    "SUPABASE_URL=$supabaseUrl"
    "SUPABASE_KEY=$supabaseKey"
    ""
    "# --- Encryption ---"
    "ENCRYPTION_KEY=$encKey"
    ""
    "# --- JWT Auth (self-hosted) ---"
    "JWT_SECRET=$jwtSecret"
    ""
    "# --- AI Copilot ---"
    "AI_BASE_URL=https://api.nexray.eu.cc/ai/gemini"
    "AI_MODEL=gemini"
    ""
    "# --- Logging ---"
    "LOG_LEVEL=INFO"
)

$lines -join "`r`n" | Out-File -FilePath "$ROOT\.env" -Encoding ascii
Write-Host "  .env created." -ForegroundColor Green

# ---- Build frontend -------------------------------------------------
Write-Host ""
Write-Host "  Building frontend..." -ForegroundColor Yellow
Set-Location $FRONTEND
npm run build
Write-Host "  Frontend built." -ForegroundColor Green

# ---- Create test user -----------------------------------------------
Write-Host ""
Write-Host "  Creating admin user..." -ForegroundColor Yellow
Set-Location $ROOT
python -c @"
from brain.db.postgres import init_db
from backend.auth.password import hash_password
from backend.auth.db import create_user, get_user_by_email

init_db()
existing = get_user_by_email('ssegawarichie72@gmail.com')
if existing:
    print('  Admin user already exists:', existing['id'])
else:
    pw = hash_password('#RichieRich206')
    user = create_user('ssegawarichie72@gmail.com', pw, 'Richie')
    if user:
        print('  Admin user created:', user['id'])
    else:
        print('  ERROR: Failed to create admin user')
"@
Write-Host "  Admin user ready." -ForegroundColor Green

# ---- Install Cloudflare Tunnel --------------------------------------
Write-Host ""
Write-Host "[9/10] Setting up Cloudflare Tunnel..." -ForegroundColor Yellow

$cfDir = "C:\cloudflared"
if (-not (Test-Path "$cfDir\cloudflared.exe")) {
    Write-Host "  Downloading cloudflared..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $cfDir | Out-Null
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile "$cfDir\cloudflared.exe"
}
$env:Path += ";$cfDir"

if (Test-Path "$env:USERPROFILE\.cloudflared\cert.pem") {
    Write-Host "  Cloudflare cert exists, skipping login." -ForegroundColor Green
} else {
    Write-Host "  Run cloudflared login on a LOCAL machine, then paste cert.pem here." -ForegroundColor Cyan
    Write-Host "  Or run: cloudflared tunnel login" -ForegroundColor Yellow
    Write-Host "  (Opens a URL — open it in your local browser)" -ForegroundColor Yellow
    cloudflared tunnel login 2>&1 | ForEach-Object { Write-Host $_ }
}

$tunnelName = "futures-bot"
Write-Host "  Creating tunnel..." -ForegroundColor Yellow
$tunnelResult = cloudflared tunnel create $tunnelName 2>&1 | Out-String
Write-Host $tunnelResult

$tunnelId = ""
if ($tunnelResult -match "id\s+(\S+)") {
    $tunnelId = $matches[1]
} elseif ($tunnelResult -match "already exists") {
    $listResult = cloudflared tunnel list 2>&1 | Out-String
    if ($listResult -match "futures-bot\s+(\S+)") {
        $tunnelId = $matches[1]
    }
}

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

if ($tunnelId) {
    cloudflared tunnel route dns $tunnelName bot.futuretraders.net 2>&1
}

cloudflared service install 2>&1 | Out-String | Write-Host
Write-Host "  Tunnel configured." -ForegroundColor Green

# ---- Register services ----------------------------------------------
Write-Host ""
Write-Host "[10/10] Registering services..." -ForegroundColor Yellow

$nssmDir = "C:\nssm"
if (-not (Test-Path "$nssmDir\nssm.exe")) {
    Write-Host "  Downloading NSSM..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $nssmDir | Out-Null
    $url = "https://www.nssm.cc/ci/nssm-2.24-101-g897c7ad.zip"
    $zip = "$env:TEMP\nssm.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "$env:TEMP\nssm_extracted" -Force
    Copy-Item "$env:TEMP\nssm_extracted\nssm-2.24-101-g897c7ad\win64\nssm.exe" "$nssmDir\nssm.exe" -Force
    Remove-Item "$env:TEMP\nssm_extracted" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $zip -ErrorAction SilentlyContinue
}

$pyPath = (Get-Command python).Source

& "$nssmDir\nssm.exe" install FuturesBot $pyPath 2>&1 | Out-Null
& "$nssmDir\nssm.exe" set FuturesBot AppParameters "backend/main.py"
& "$nssmDir\nssm.exe" set FuturesBot AppDirectory "$ROOT"
& "$nssmDir\nssm.exe" set FuturesBot DisplayName "FUTURES Trading Bot"
& "$nssmDir\nssm.exe" set FuturesBot Description "AI-Powered Forex Trading Bot"
& "$nssmDir\nssm.exe" set FuturesBot Start SERVICE_AUTO_START
Write-Host "  Bot service registered." -ForegroundColor Green

# ---- Start everything -----------------------------------------------
Write-Host ""
Write-Host "  Starting services..." -ForegroundColor Yellow
& "$nssmDir\nssm.exe" start FuturesBot
net start cloudflared 2>$null

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SETUP COMPLETE!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend:  https://bot.futuretraders.net" -ForegroundColor Green
Write-Host "  Login:    ssegawarichie72@gmail.com" -ForegroundColor Yellow
Write-Host "  Password: #RichieRich206" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Services:" -ForegroundColor White
Write-Host "    nssm start/stop/restart FuturesBot" -ForegroundColor Yellow
Write-Host "    net start/stop cloudflared" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Logs: C:\futures\brain\logs\futuresbrain.log" -ForegroundColor White
Write-Host ""
Write-Host "  To update later:" -ForegroundColor White
Write-Host "    cd C:\futures && git pull && pip install -r requirements.txt" -ForegroundColor Yellow
Write-Host "    cd C:\futures-frontend && git pull && npm run build" -ForegroundColor Yellow
Write-Host "    nssm restart FuturesBot" -ForegroundColor Yellow
Write-Host ""
Write-Host "  VYLUX TECH / RICHIE RICH" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Cyan
