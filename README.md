<p align="center">
  <img src="web/assets/images/logo.jpg" alt="FUTURES Logo" width="220">
</p>

<h1 align="center">FUTURES Trading Bot</h1>

<p align="center">
  <b>AI-Powered Automated Forex Trading Platform</b>
  <br>
  Built for precision. Driven by intelligence. Designed for scale.
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#tech-stack">Stack</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#credits">Credits</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Supabase-3FCF8E?style=flat-square&logo=supabase&logoColor=white">
  <img src="https://img.shields.io/badge/MetaTrader-5-00BFFF?style=flat-square&logo=meta&logoColor=white">
  <img src="https://img.shields.io/badge/AI-DeepSeek-FF6F00?style=flat-square&logo=deepseek&logoColor=white">
  <img src="https://img.shields.io/badge/Cloudflare-Tunnel-F38020?style=flat-square&logo=cloudflare&logoColor=white">
</p>

---

## <a id="features"></a>What It Does

<p align="center">
  <table>
    <tr>
      <td align="center" width="33%">
        <strong>AI Market Analysis</strong><br>
        <sub>DeepSeek-powered analysis across 6 forex pairs with real-time signal generation</sub>
      </td>
      <td align="center" width="33%">
        <strong>Chart Vision</strong><br>
        <sub>Qwen2.5-VL reads your charts — the AI sees what you see</sub>
      </td>
      <td align="center" width="33%">
        <strong>Copilot Chat</strong><br>
        <sub>Natural conversation with your trading AI. No commands. Just talk.</sub>
      </td>
    </tr>
    <tr>
      <td align="center" width="33%">
        <strong>Auto Trading</strong><br>
        <sub>MT5 integration with configurable risk, BE policy, and drawdown protection</sub>
      </td>
      <td align="center" width="33%">
        <strong>Multi-User</strong><br>
        <sub>Supabase auth + RLS. Every user sees only their trades.</sub>
      </td>
      <td align="center" width="33%">
        <strong>Responsive Web App</strong><br>
        <sub>Mobile-first dashboard — no app store, no build step</sub>
      </td>
    </tr>
    <tr>
      <td align="center" width="33%">
        <strong>8-Sector Pipeline</strong><br>
        <sub>Multi-factor market evaluation for high-conviction signals</sub>
      </td>
      <td align="center" width="33%">
        <strong>Telegram Admin</strong><br>
        <sub>Monitor trades, health, and risk — from your phone</sub>
      </td>
      <td align="center" width="33%">
        <strong>Risk Guardrails</strong><br>
        <sub>Max drawdown, cooldowns, spread checks. The bot respects your limits.</sub>
      </td>
    </tr>
  </table>
</p>

---

## <a id="tech-stack"></a>Built With

| Layer | Tech |
|-------|------|
| **Backend** | Python 3.11+ • FastAPI • asyncio |
| **Database** | Supabase (PostgreSQL) • Row Level Security |
| **AI Engine** | DeepSeek LLM • Qwen2.5-VL • Custom Workers AI endpoint |
| **Trading** | MetaTrader 5 • HFM |
| **Frontend** | Vanilla HTML / CSS / JavaScript (zero dependencies) |
| **Auth** | Supabase Auth • JWT • Encrypted credentials (Fernet) |
| **Infra** | Cloudflare Tunnel • Windows VPS • NSSM |
| **Admin** | Telegram Bot • Real-time health monitoring |

---

## <a id="quick-start"></a>Get Started in 30 Seconds

```bash
git clone https://github.com/VYLUXTECHINC/FUTURES.git
cd FUTURES
cp .env.example .env
pip install -r backend/requirements.txt
python backend/main.py
```

> Edit `.env` first with your Supabase credentials and AI endpoint. Full setup guide in [`VPS-SETUP.md`](VPS-SETUP.md).

---

## <a id="architecture"></a>How It Works

```
Users ── HTTPS ── Cloudflare Tunnel ── FastAPI ── Supabase
                    (outbound only)       │
                                         └── MT5 ── HFM
```

1. Users sign up and connect their MT5 account
2. The bot reads credentials from Supabase, logs into MT5
3. The 8-sector pipeline evaluates the market every 15m
4. High-conviction signals are executed automatically
5. All trades, PnL, and settings sync to Supabase in real-time

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Service role key (backend only) |
| `SUPABASE_JWT_SECRET` | For JWT verification |
| `SUPABASE_DB_URI` | PostgreSQL connection string |
| `ENCRYPTION_KEY` | Fernet key for MT5 password encryption |
| `AI_BASE_URL` | Custom Workers AI endpoint |
| `AI_MODEL` | LLM model (`deepseek`) |
| `HF_TOKEN` | Hugging Face API token (vision) |
| `HF_VISION_MODEL` | HF vision model ID |

---

## Project Structure

```
FUTURES/
├── backend/          FastAPI server, auth API, AI copilot
├── brain/            Core trading engine (pipeline, risk, MT5)
├── web/              Static frontend SPA
├── db.txt            Supabase SQL schema
└── VPS-SETUP.md      Production deployment guide
```

---

## <a id="credits"></a>Credits

<table>
  <tr>
    <td align="center">
      <strong>VYLUX TECH</strong><br>
      <sub>Development & Architecture</sub>
    </td>
    <td align="center">
      <strong>RICHIE RICH</strong><br>
      <sub>Concept & Vision</sub>
    </td>
  </tr>
</table>

---

<p align="center">
  <sub>Automated trading involves financial risk. Trade at your own discretion.</sub>
  <br>
  <sub>Built with ❤️ for the futures market</sub>
</p>
