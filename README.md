<p align="center">
  <img src="web/assets/images/logo.jpg" alt="FUTURES Logo" width="200">
</p>

# FUTURES Trading Bot

An automated futures trading platform powered by AI-driven market analysis, real-time signals, and a responsive web dashboard.

## Features

- **AI-Powered Analysis** — Market analysis using DeepSeek LLM via custom AI endpoint
- **Chart Vision** — Qwen-VL integration for technical chart interpretation
- **Natural Language Copilot** — Conversational AI assistant for trade insights
- **Real-Time Trading** — MT5 integration for automated execution
- **Responsive Dashboard** — Mobile-first web interface served by FastAPI
- **User Management** — Supabase auth with profile settings & broker verification
- **Multi-Sector Analysis** — 8-sector market evaluation pipeline
- **Risk Management** — Configurable risk per trade, BE policy, loss cooldown

## Tech Stack

| Layer   | Stack |
|---------|-------|
| Backend | Python, FastAPI, asyncio |
| Database| Supabase (PostgreSQL) |
| AI      | DeepSeek + Qwen2.5-VL via Workers AI |
| Trading | MetaTrader 5 |
| Frontend| Vanilla HTML/JS/CSS (no framework) |
| Auth    | Supabase Auth + JWT |
| Admin   | Telegram Bot |

## Quick Start

```bash
# Clone
git clone https://github.com/VYLUXTECHINC/FUTURES.git
cd FUTURES

# Set up environment
cp .env.example .env
# Edit .env with your Supabase credentials, AI endpoint, etc.

# Install dependencies
pip install -r backend/requirements.txt

# Run
python backend/main.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `AI_BASE_URL` | Custom AI endpoint URL |
| `AI_MODEL` | AI model name (e.g. `deepseek`) |
| `HF_TOKEN` | Hugging Face API token (for vision) |
| `HF_VISION_MODEL` | HF vision model ID |

## Project Structure

```
backend/         — FastAPI server & AI modules
brain/           — Core trading engine (pipeline, risk, execution)
web/             — Static frontend (index.html, main.js, style.css)
db.txt           — Supabase SQL schema
```

## Credits

**VYLUX TECH** — Development & architecture  
**RICHIE RICH** — Concept & vision

---

*Automated trading involves financial risk. Use at your own discretion.*
