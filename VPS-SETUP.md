# FUTURES Trading Bot — Production VPS Setup Guide

## Prerequisites

- Windows Server 2019/2022 VPS (minimum 2 CPU, 4GB RAM, 40GB SSD)
- HFM MT5 account (Demo or Live)
- Supabase project set up and migrations executed
- Domain name with access to DNS settings (e.g., Cloudflare, Namecheap, GoDaddy)

---

## Step 1: Point Your Subdomain to the VPS

### 1.1 Get Your VPS Public IP

Log into your VPS provider dashboard and note the **public IPv4 address** (e.g., `203.0.113.50`).

### 1.2 Add DNS Record

Go to your domain registrar or DNS provider (Cloudflare recommended) and add:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `bot` (or your subdomain) | `203.0.113.50` | Auto |

This creates `bot.yourdomain.com` pointing to your VPS.

**Examples:**
- Cloudflare: DNS → Add Record → A → Name: `bot` → Content: your VPS IP → Proxy: Proxied (orange cloud)
- Namecheap: Advanced DNS → Add New Record → A Record → Host: `bot` → Value: your VPS IP
- GoDaddy: DNS Management → Add → A → Name: `bot` → Points to: your VIP IP

### 1.3 Verify DNS Propagation

```cmd
nslookup bot.yourdomain.com
```

Should return your VPS IP. Propagation takes 1-48 hours (usually minutes with Cloudflare).

---

## Step 2: Install Python

1. Download Python 3.11+ from https://www.python.org/downloads/windows/
2. Run installer → **Check "Add Python to PATH"** → Install Now
3. Verify: Open Command Prompt → `python --version`

---

## Step 3: Install HFM MetaTrader 5

1. Download HFM MT5 from: https://www.hfm.com/en/trading-platforms/metatrader-5
2. Run installer → Install to default location (`C:\Program Files\HFM MetaTrader 5\`)
3. **Launch MT5 once** → File → Open an Account → Select your server:
   - **Demo:** `HFM.com Demo MT5`
   - **Live:** `HFM.com Real MT5`
4. Log in with your MT5 credentials
5. **Enable Algo Trading:**
   - Tools → Options → Expert Advisors
   - ✅ Check "Allow Algorithmic Trading"
   - ✅ Check "Allow WebRequest for listed URLs"
   - Add: `https://qebzhaqhdchanqvrhijb.supabase.co`
   - Click OK
6. Close MT5 (the bot will launch it automatically)

---

## Step 4: Set Up the Bot

### 4.1 Clone/Upload Your Project

```cmd
cd C:\
mkdir futures-bot
```

Upload your project files to `C:\futures-bot\` (via RDP file copy, Git, or SCP).

### 4.2 Install Dependencies

```cmd
cd C:\futures-bot
pip install -r requirements.txt
```

### 4.3 Generate Encryption Key

MT5 passwords are encrypted before storage. Generate a key:

```cmd
python -c "from cryptography.fernet import Fernet; import base64; print(base64.urlsafe_b64encode(Fernet.generate_key()).decode())"
```

Copy the output — you'll need it in `.env`.

### 4.4 Configure `.env`

Create `C:\futures-bot\.env` with your actual values:

```env
# --- API ---
API_HOST=127.0.0.1
API_PORT=8000

# --- Allowed Origins (your subdomain + app URLs) ---
ALLOWED_ORIGINS=https://bot.yourdomain.com,http://localhost:3000,http://localhost:8081

# --- Supabase ---
SUPABASE_URL=https://qebzhaqhdchanqvrhijb.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_DB_URI=postgresql://postgres.qebzhaqhdchanqvrhijb:joKwagala256@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
SUPABASE_JWT_SECRET=your-jwt-secret-here

# --- Encryption (generated in Step 4.3) ---
ENCRYPTION_KEY=your-generated-encryption-key-here

# --- Expo App ---
EXPO_PUBLIC_SUPABASE_URL=https://qebzhaqhdchanqvrhijb.supabase.co
EXPO_PUBLIC_SUPABASE_KEY=your-anon-key-here

# --- OpenRouter / AI ---
OPENROUTER_API_KEY=your-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# --- Logging ---
LOG_LEVEL=INFO

# --- Telegram Admin ---
TELEGRAM_ADMIN_BOT_TOKEN=your-bot-token
TELEGRAM_ADMIN_ID_1=your-telegram-id
TELEGRAM_ADMIN_ID_2=your-second-telegram-id
```

**Important:** Replace `bot.yourdomain.com` with your actual subdomain.

---

## Step 5: Set Up Reverse Proxy with Caddy (HTTPS)

Caddy automatically obtains and renews SSL certificates. This is the easiest way to get HTTPS.

### 5.1 Download Caddy

1. Download Caddy for Windows from: https://caddyserver.com/download
2. Extract `caddy.exe` to `C:\caddy\`

### 5.2 Create Caddyfile

Create `C:\caddy\Caddyfile` (no extension):

```
bot.yourdomain.com {
    reverse_proxy 127.0.0.1:8000

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
```

Replace `bot.yourdomain.com` with your actual subdomain.

### 5.3 Run Caddy

```cmd
cd C:\caddy
caddy run
```

Caddy will:
- Obtain an SSL certificate from Let's Encrypt automatically
- Proxy all HTTPS traffic to your bot on port 8000
- Redirect HTTP to HTTPS automatically

### 5.4 Test HTTPS

Open `https://bot.yourdomain.com` in your browser. You should see a padlock icon.

---

## Step 6: Alternative — Nginx Reverse Proxy (if you prefer)

### 6.1 Install Nginx

Download from: http://nginx.org/en/download.html (Windows version)

Extract to `C:\nginx\`

### 6.2 Configure Nginx

Edit `C:\nginx\conf\nginx.conf`:

```nginx
server {
    listen 80;
    server_name bot.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bot.yourdomain.com;

    # SSL certificates (obtain via Certbot or manual)
    ssl_certificate     C:/nginx/ssl/cert.pem;
    ssl_certificate_key C:/nginx/ssl/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Proxy to bot
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 6.3 Get SSL Certificates

Use Certbot or your domain registrar's SSL certificates. Place them in `C:\nginx\ssl\`.

---

## Step 7: Configure Firewall

### 7.1 Windows Firewall

Only allow ports 80 and 443 from the internet. Port 8000 should only be accessible locally.

```cmd
# Allow HTTP (for Caddy/Nginx)
netsh advfirewall firewall add rule name="HTTP" dir=in action=allow protocol=TCP localport=80

# Allow HTTPS
netsh advfirewall firewall add rule name="HTTPS" dir=in action=allow protocol=TCP localport=443

# Block port 8000 from external access (allow only localhost)
netsh advfirewall firewall add rule name="Block API Port" dir=in action=block protocol=TCP localport=8000 remoteip=any
```

### 7.2 Cloudflare (if using)

- Enable "Proxy status: Proxied" (orange cloud) in DNS settings
- Enable "Always Use HTTPS" in SSL/TLS → Edge Certificates
- Enable "Automatic HTTPS Rewrites"

---

## Step 8: Save MT5 Credentials via the App

1. Open your Expo app on phone/web
2. Sign up → Verify email → Go to Broker Connect
3. Create HFM account (via referral) → Verify email → Login
4. Enter your **MT5 Login ID**, **Password**, and select **Demo** or **Live**
5. Tap "Activate Trading Bot"

This saves your credentials to Supabase (encrypted) with the correct server format.

---

## Step 9: Test the Connection

```cmd
cd C:\futures-bot
python backend/main.py
```

Watch the console output. You should see:
```
✅ MT5 connected on attempt 1 | login=50123456 | server=HFM.com Demo MT5 | type=DEMO | build=4000
Trading loop active | pairs=['GBPUSD', 'GBPJPY', 'USDJPY'] | tf=15m
```

---

## Step 10: Run as a Windows Service (Auto-Start on Boot)

### Option A: Using NSSM (Recommended)

1. Download NSSM: https://nssm.cc/download
2. Extract to `C:\nssm\`
3. Install the bot as a service:

```cmd
C:\nssm\win64\nssm install FuturesBot
```

Configure:
- **Path:** `C:\Python311\python.exe` (your Python path)
- **Startup directory:** `C:\futures-bot`
- **Arguments:** `backend/main.py`
- **Details tab:** Display name = "FUTURES Trading Bot"
- **Log on tab:** Select "Local System account"

4. Start the service:

```cmd
nssm start FuturesBot
```

5. Verify: `nssm status FuturesBot` → should show `SERVICE_RUNNING`

### Option B: Using Task Scheduler

1. Open Task Scheduler → Create Task
2. **General:** Run whether user is logged on or not, Run with highest privileges
3. **Triggers:** At startup
4. **Actions:** Start a program
   - Program: `C:\Python311\python.exe`
   - Arguments: `C:\futures-bot\backend/main.py`
   - Start in: `C:\futures-bot`
5. **Conditions:** Uncheck "Start only on AC power"
6. **Settings:** Check "Allow task to be run on demand"

### Option C: Run Caddy as Service (for HTTPS)

```cmd
C:\nssm\win64\nssm install CaddyProxy
```

Configure:
- **Path:** `C:\caddy\caddy.exe`
- **Startup directory:** `C:\caddy`
- **Arguments:** `run`

```cmd
nssm start CaddyProxy
```

---

## Step 11: Verify Everything Works

### Check Bot Status via API

```cmd
curl https://bot.yourdomain.com/api/status
```

Expected response:
```json
{
  "running": true,
  "connected": true,
  "mt5_connected": true,
  "account_balance": 10000.0,
  "equity": 10000.0,
  "daily_trades": 0,
  "daily_pnl": 0.0,
  "cooldown_active": false,
  "pairs": ["GBPUSD", "GBPJPY", "USDJPY"],
  "session_active": true,
  "risk_percent": 5.0
}
```

### Check via Telegram Bot

Send `/health` to your Telegram admin bot.

### Check via Expo App

Update your Expo app's `EXPO_PUBLIC_API_URL` to `https://bot.yourdomain.com/api` and rebuild.

---

## Trading Modes

### Short Mode (Default)
- Takes one trade at a time
- Waits for position to close before taking next signal
- Best for conservative trading

### Long Term Mode
- Allows multiple concurrent positions
- Auto-compounding enabled (profits increase lot sizes)
- Runs continuously during trading sessions
- Best for aggressive growth

To switch modes, use the API or app settings:
```json
POST /api/user/start
{
  "mode": "long",
  "risk_percent": 5,
  "auto_compounding": true
}
```

---

## Multi-MT5 Account Support

The bot supports multiple MT5 accounts. You can:

1. **List all accounts:**
   ```
   GET /api/mt5/accounts
   ```

2. **Switch between accounts:**
   ```
   POST /api/mt5/switch
   {
     "login": "50123456",
     "server": "HFM.com Demo MT5"
   }
   ```

3. **Connect a new account:**
   Use the app's Broker Connect page or:
   ```
   POST /api/mt5/connect
   {
     "login": "50123456",
     "password": "your-password",
     "server": "HFM.com Demo MT5",
     "account_name": "My Demo Account"
   }
   ```

---

## Troubleshooting

### MT5 Connection Fails
```
❌ MT5 connection failed after 5 attempts
```
- Open MT5 manually → verify you can log in
- Check server name matches **exactly** (case-sensitive)
- Check "Allow Algorithmic Trading" is enabled
- Kill any running MT5 processes: `taskkill /F /IM terminal64.exe`
- Try again

### SSL Certificate Issues
- Ensure port 80 is open (Caddy needs it for Let's Encrypt challenge)
- Check DNS is pointing to correct IP: `nslookup bot.yourdomain.com`
- If using Cloudflare, set SSL/TLS mode to "Full" or "Full (strict)"

### No Trades Being Placed
- Check trading session: UTC 06:00-20:00 only (Mon-Fri)
- Check no open positions already exist (in short mode, bot only trades 1 at a time)
- Check risk gates: cooldown, drawdown, news, ATR spike
- Check logs: `C:\futures-bot\logs\` (if configured)

### Bot Crashes on Start
- Verify Python version: `python --version` (need 3.8+)
- Verify all pip packages installed: `pip install -r requirements.txt`
- Verify `.env` file has all required variables
- Check Supabase connection: `python -c "import psycopg2; psycopg2.connect('your-db-uri')"`

### CORS Errors from App
- Update `ALLOWED_ORIGINS` in `.env` to include your subdomain
- Restart the bot after changing `.env`

### Server Name Issues
If `HFM.com Demo MT5` doesn't work, try these alternatives:
- `HFMGlobal-Demo`
- `HFM-Demo`
- `HFMDemo`
- `HFM.com Real MT5` → `HFMGlobal-Real`

Find the exact name by opening MT5 → File → Login to Trade Account → look at the Server dropdown.

---

## Security Checklist

- [ ] `.env` file is NOT committed to Git
- [ ] `ALLOWED_ORIGINS` only includes your domain
- [ ] HTTPS is enabled (padlock in browser)
- [ ] MT5 passwords are encrypted in database
- [ ] Windows Firewall blocks port 8000 from external access
- [ ] Supabase RLS policies are active
- [ ] `ENCRYPTION_KEY` is unique and stored securely
- [ ] `SUPABASE_JWT_SECRET` is configured for proper auth
- [ ] Telegram admin IDs are set to your IDs only

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python backend/main.py` | Start bot manually |
| `nssm start FuturesBot` | Start bot service |
| `nssm stop FuturesBot` | Stop bot service |
| `nssm status FuturesBot` | Check service status |
| `curl https://bot.yourdomain.com/api/status` | Check bot status |
| `taskkill /F /IM terminal64.exe` | Kill MT5 |
| `pip install -r requirements.txt` | Install dependencies |
| `caddy run` | Start HTTPS reverse proxy |
| `nssm start CaddyProxy` | Start Caddy as service |
