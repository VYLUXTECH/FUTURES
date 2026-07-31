<h1 align="center">THE DISCIPLE</h1>

<p align="center">
  <i>"Embrace the eccentricity of price"</i>
</p>

<p align="center">
  <b>AI-Powered Automated Forex Trading Platform</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/MetaTrader-5-00BFFF?style=flat-square&logo=meta&logoColor=white">
  <img src="https://img.shields.io/badge/AI-Gemini-4285F4?style=flat-square&logo=google&logoColor=white">
  <img src="https://img.shields.io/badge/Cloudflare-Tunnel-F38020?style=flat-square&logo=cloudflare&logoColor=white">
</p>

---

## Features

- **8-Sector Pipeline** - Multi-factor market evaluation for high-conviction signals
- **AI Copilot** - Natural language chat with your trading bot
- **Auto Trading** - MT5 integration with configurable risk and drawdown protection
- **Multi-User** - Self-hosted JWT auth + PostgreSQL. Each user sees only their trades.
- **Risk Guardrails** - Max drawdown, cooldowns, spread checks
- **Responsive Web App** - Mobile-first dashboard (separate repo: `VYLUXTECH/futures-frontend`)

---

## Quick Start (Windows VPS)

Open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope Process -Force
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/VYLUXTECH/THE-DISCIPLE/main/scripts/fresh-setup.ps1" -OutFile "$env:TEMP\go.ps1"
& "$env:TEMP\go.ps1"
```

It will ask for your PostgreSQL connection string (`SUPABASE_DB_URI`). Everything else is auto-generated.

> No Supabase service — the backend talks to PostgreSQL directly via psycopg2.

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SUPABASE_DB_URI` | PostgreSQL connection string |
| `JWT_SECRET` | Self-hosted JWT auth secret |
| `ENCRYPTION_KEY` | Fernet key for MT5 password encryption |
| `AI_BASE_URL` | Gemini AI endpoint |
| `AI_MODEL` | LLM model |

---

## Architecture

```
Users -- HTTPS -- Cloudflare Tunnel -- FastAPI -- PostgreSQL
                    (outbound only)       |
                                         +-- MT5 -- HFM
```

---

## Credits

| | |
|---|---|
| **VYLUX TECH** | Development & Architecture |
| **RICHIE RICH** | Concept & Vision |

---

<p align="center">
  <sub>Automated trading involves financial risk. Trade at your own discretion.</sub>
</p>
