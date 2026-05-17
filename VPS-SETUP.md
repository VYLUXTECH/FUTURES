# FUTURES Trading Bot — Windows VPS Setup Guide

## Prerequisites

- Windows Server 2019/2022 VPS (minimum 2 CPU, 4GB RAM)
- HFM MT5 account (Demo or Live)
- Your Supabase project set up and `db.txt` SQL executed

---

## Step 1: Install Python

1. Download Python 3.11+ from https://www.python.org/downloads/windows/
2. Run installer → **Check "Add Python to PATH"** → Install Now
3. Verify: Open Command Prompt → `python --version`

---

## Step 2: Install HFM MetaTrader 5

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

## Step 3: Find Your Exact Server Name

This is **critical** — the server name must match exactly what MT5 shows.

1. Open MT5 → File → Login to Trade Account
2. Look at the **Server** dropdown — note the **exact** name:
   - Common HFM servers:
     - `HFM.com Demo MT5` (Demo)
     - `HFM.com Real MT5` (Live/Real)
     - `HFMGlobal-Demo` (Demo alternative)
     - `HFMGlobal-Real` (Live alternative)
3. **Write down the exact server name** — you'll need it

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

### 4.3 Configure `.env`

Edit `C:\futures-bot\.env` with your actual values:

```env
# --- API ---
API_HOST=0.0.0.0
API_PORT=8000

# --- Supabase ---
SUPABASE_URL=https://qebzhaqhdchanqvrhijb.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_DB_URI=postgresql://postgres.qebzhaqhdchanqvrhijb:joKwagala256@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

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

### 4.4 Set MT5 Path (if non-standard install)

If MT5 is not in a standard location, add to `.env`:

```env
MT5_PATH=C:\Path\To\Your\MT5\terminal64.exe
```

---

## Step 5: Save MT5 Credentials via the App

1. Open your Expo app on phone/web
2. Sign up → Verify email → Go to Broker Connect
3. Create HFM account (via referral) → Verify email → Login
4. Enter your **MT5 Login ID**, **Password**, and select **Demo** or **Live**
5. Tap "Activate Trading Bot"

This saves your credentials to Supabase with the correct server format:
- Demo → `HFM.com Demo MT5`
- Live → `HFM.com Real MT5`

---

## Step 6: Test the Connection

```cmd
cd C:\futures-bot
python backend/main.py
```

Watch the console output. You should see:
```
✅ MT5 connected on attempt 1 | login=50123456 | server=HFM.com Demo MT5 | type=DEMO | build=4000
Trading loop active | pairs=['GBPUSD', 'GBPJPY', 'USDJPY'] | tf=15m
```

If you see `❌ MT5 connection failed`, check:
- Server name matches exactly (Step 3)
- MT5 was launched at least once
- "Allow Algorithmic Trading" is enabled in MT5
- MT5 is not already running with a different account

---

## Step 7: Run as a Windows Service (Auto-Start on Boot)

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

---

## Step 8: Verify Everything Works

### Check Bot Status via API

```cmd
curl http://localhost:8000/api/status
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

Open the app → Dashboard → Should show:
- Green health dot
- Account balance
- Bot status: Running

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

### No Trades Being Placed
- Check trading session: UTC 06:00-20:00 only (Mon-Fri)
- Check no open positions already exist (bot only trades 1 at a time)
- Check risk gates: cooldown, drawdown, news, ATR spike
- Check logs: `C:\futures-bot\logs\` (if configured)

### Bot Crashes on Start
- Verify Python version: `python --version` (need 3.8+)
- Verify all pip packages installed: `pip install -r requirements.txt`
- Verify `.env` file has all required variables
- Check Supabase connection: `python -c "import psycopg2; psycopg2.connect('your-db-uri')"`

### Server Name Issues
If `HFM.com Demo MT5` doesn't work, try these alternatives:
- `HFMGlobal-Demo`
- `HFM-Demo`
- `HFMDemo`
- `HFM.com Real MT5` → `HFMGlobal-Real`

Find the exact name by opening MT5 → File → Login to Trade Account → look at the Server dropdown.

---

## Security Notes

- **Never share** your `.env` file
- **Never commit** `.env` to Git
- MT5 passwords are stored in Supabase — ensure RLS policies are active
- Use a Windows firewall rule to only allow inbound on port 8000 from your IP
- Consider using HTTPS with a reverse proxy (nginx/Caddy) for production

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python backend/main.py` | Start bot manually |
| `nssm start FuturesBot` | Start bot service |
| `nssm stop FuturesBot` | Stop bot service |
| `nssm status FuturesBot` | Check service status |
| `curl http://localhost:8000/api/status` | Check bot status |
| `taskkill /F /IM terminal64.exe` | Kill MT5 |
| `pip install -r requirements.txt` | Install dependencies |
