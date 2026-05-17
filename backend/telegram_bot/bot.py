from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from backend.telegram_bot.supabase_admin import (
    get_health,
    get_users,
    get_user_detail,
    stop_user,
    global_shutdown,
    get_issues,
    resolve_issue,
    get_stats,
    broadcast_to_all,
    get_daily_report,
)

load_dotenv()

logger = logging.getLogger(__name__)

# ── Environment ────────────────────────────────────────────
BOT_TOKEN: str | None = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
ADMIN_ID_1: int = int(os.getenv("TELEGRAM_ADMIN_ID_1", "0"))
ADMIN_ID_2: int = int(os.getenv("TELEGRAM_ADMIN_ID_2", "0"))

ALLOWED_IDS: frozenset[int] = frozenset({ADMIN_ID_1, ADMIN_ID_2} - {0})

POLL_INTERVAL = 60
DAILY_REPORT_HOUR = 0
DAILY_REPORT_MINUTE = 5

# ── In-memory state ──────────────────────────────────────
_pending_confirm: dict[int, dict[str, Any]] = {}
_sent_issue_ids: set[int] = set()
_cooldown_notified: set[str] = set()
_last_daily_report: str | None = None
_stop_event = asyncio.Event()

# ── Helpers ────────────────────────────────────────────────

def _is_authorized(user_id: int) -> bool:
    if not ALLOWED_IDS:
        return False
    return user_id in ALLOWED_IDS


def _format_user(u: dict[str, Any]) -> str:
    email = u.get("email", u.get("id", "?"))
    uid = u.get("id", "?")
    active = "Yes" if u.get("bot_active") else "No"
    daily = f'{u.get("daily_trades_used", 0)}/5'
    cd = u.get("cooldown_until") or "None"
    balance = u.get("mt5_balance", "N/A")
    return (
        f"  ID: {uid}\n"
        f"  Email: {email}\n"
        f"  Balance (MT5): ${balance}\n"
        f"  Bot active: {active}\n"
        f"  Daily used: {daily}\n"
        f"  Cooldown: {cd}"
    )


async def _send(update: Update, text: str) -> None:
    await update.message.reply_text(text, disable_web_page_preview=True)


# ── Health / Status ────────────────────────────────────────

async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    health = get_health()
    if "error" in health:
        await _send(update, f"❌ {health['error']}")
        return

    lines = [
        "🤖 FUTURES System Health",
        "─────────────────────",
        f"Active users: {health.get('active_users', 'N/A')}",
        f"Trades last 24h: {health.get('trades_24h', 'N/A')}",
        f"Net P&L last 24h: ${health.get('pnl_24h', 'N/A')}",
        f"Win rate (30d): {health.get('win_rate_30d', 'N/A')}",
        f"Net P&L (30d): ${health.get('net_pnl_30d', 'N/A')}",
        f"News monitor: {health.get('news_monitor', 'N/A')}",
        f"Last error: {health.get('last_error') or 'None'}",
    ]
    await _send(update, "\n".join(lines))


# ── Users ──────────────────────────────────────────────────

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    users = get_users()
    if not users:
        await _send(update, "👥 No users found.")
        return

    lines = ["👥 Registered Users", "──────────────────"]
    for i, u in enumerate(users[:20], 1):
        email = u.get("email", u.get("id", "?"))
        active = "Yes" if u.get("bot_active") else "No"
        daily = f'{u.get("daily_trades_used", 0)}/5'
        cd = u.get("cooldown_until") or "None"
        lines.append(f"{i}. {email} | Active: {active} | Daily: {daily} | Cooldown: {cd}")

    if len(users) > 20:
        lines.append(f"\n... and {len(users) - 20} more")
    await _send(update, "\n".join(lines))


async def cmd_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await _send(update, "Usage: /user <user_id>")
        return

    user_id = parts[1].strip()
    user = get_user_detail(user_id)
    if user is None:
        await _send(update, "❌ User not found.")
        return

    open_pos = user.get("open_positions", [])
    pos_lines = []
    for t in open_pos:
        pos_lines.append(f"{t.get('pair', '?')} {t.get('direction', '?')} ${t.get('pnl', 0):.2f}")

    lines = [
        f"📊 User Detail",
        "─────────────────",
        _format_user(user),
    ]
    if pos_lines:
        lines.append(f"  Open positions: {', '.join(pos_lines)}")
    else:
        lines.append("  Open positions: None")
    await _send(update, "\n".join(lines))


async def cmd_stop_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await _send(update, "Usage: /stop_user <user_id>")
        return

    target = parts[1].strip()
    user = get_user_detail(target)
    if user is None:
        await _send(update, "❌ User not found.")
        return

    email = user.get("email", target)
    _pending_confirm[uid] = {"action": "stop_user", "user_id": target, "email": email}
    await _send(update, (
        f"⚠️ Stop bot for user {email}?\n"
        "This will close all positions.\n"
        "Reply CONFIRM to proceed."
    ))


# ── Broadcast ──────────────────────────────────────────────

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await _send(update, "Usage: /broadcast <message>")
        return

    message = parts[1].strip()
    sent, errors = broadcast_to_all("FUTURES Announcement", message)
    if sent:
        await _send(update, f"📢 Broadcast sent to {sent} users" + (f" ({errors} errors)" if errors else ""))
    else:
        await _send(update, "⚠️ No active users to broadcast to.")


# ── Issues ─────────────────────────────────────────────────

async def cmd_issues(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    issues = get_issues()
    if not issues:
        await _send(update, "🎫 No unresolved issues.")
        return

    lines = ["🎫 Unresolved Issues", "───────────────────"]
    for i, iss in enumerate(issues, 1):
        title = iss.get("title", iss.get("subject", "?"))
        uid_str = iss.get("user_id", "?")
        created = (iss.get("created_at") or "")[:16]
        lines.append(f'{i}. [{uid_str}] "{title}" - {created}')
    await _send(update, "\n".join(lines))


async def cmd_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await _send(update, "Usage: /resolve <issue_id>")
        return

    try:
        issue_id = int(parts[1].strip())
    except ValueError:
        await _send(update, "❌ Issue ID must be a number.")
        return

    if resolve_issue(issue_id):
        await _send(update, f"✅ Issue #{issue_id} resolved.")
    else:
        await _send(update, f"❌ Failed to resolve issue #{issue_id}.")


# ── Control ────────────────────────────────────────────────

async def cmd_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    _pending_confirm[uid] = {"action": "shutdown"}
    await _send(update, (
        "⚠️ GLOBAL EMERGENCY STOP will close ALL positions for ALL users.\n"
        "Reply CONFIRM (in capital letters) to proceed."
    ))


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    await _send(update, "🔄 Restarting trading engine...")
    os._exit(42)


# ── Stats ──────────────────────────────────────────────────

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    days = 30
    parts = (update.message.text or "").split()
    if len(parts) >= 2:
        try:
            days = int(parts[1])
        except ValueError:
            pass

    stats = get_stats(days)
    if "error" in stats:
        await _send(update, f"❌ {stats['error']}")
        return

    lines = [
        f"📈 FUTURES Trading Statistics (Last {stats.get('period_days', 30)} Days)",
        "───────────────────────────────────────────",
        f"Total trades: {stats.get('total_trades', 'N/A')}",
        f"Winning trades: {stats.get('wins', 'N/A')} ({stats.get('win_rate', 'N/A')})",
        f"Losing trades: {stats.get('losses', 'N/A')}",
        f"Net P&L: ${stats.get('net_pnl', 'N/A')}",
        f"Profit factor: {stats.get('profit_factor', 'N/A')}",
        f"Average win: ${stats.get('avg_win', 0)}",
        f"Average loss: ${stats.get('avg_loss', 0)}",
        f"Largest win: ${stats.get('largest_win', 0)}",
        f"Largest loss: ${stats.get('largest_loss', 0)}",
    ]
    await _send(update, "\n".join(lines))


# ── Help ───────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    text = (
        "🤖 FUTURES Admin Bot – Commands\n"
        "───────────────────────────────\n"
        "\n"
        "📊 System:\n"
        "  /health or /status – System health & metrics\n"
        "  /stats [days] – Detailed trading statistics\n"
        "\n"
        "👥 Users:\n"
        "  /users – List all users\n"
        "  /user <id> – Show user details\n"
        "  /stop_user <id> – Stop bot for a specific user\n"
        "\n"
        "📢 Broadcast:\n"
        "  /broadcast <msg> – Send notification to all users\n"
        "\n"
        "🎫 Support:\n"
        "  /issues – List unresolved issues\n"
        "  /resolve <id> – Mark issue as resolved\n"
        "\n"
        "🛑 Control:\n"
        "  /shutdown – Global emergency stop (all users)\n"
        "  /restart – Restart trading engine\n"
        "\n"
        "──────────────────────────────\n"
        "Authorised for Telegram user IDs only."
    )
    await _send(update, text)


# ── CONFIRM handler ────────────────────────────────────────

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return

    text = (update.message.text or "").strip()
    if text != "CONFIRM":
        return

    pending = _pending_confirm.pop(uid, None)
    if pending is None:
        return

    action = pending.get("action")

    if action == "stop_user":
        target = pending.get("user_id", "")
        ok = stop_user(target)
        email = pending.get("email", target)
        if ok:
            await _send(update, f"✅ Bot stopped for user {email}.")
        else:
            await _send(update, f"❌ Failed to stop bot for user {email}.")

    elif action == "shutdown":
        ok = global_shutdown()
        if ok:
            await _send(update, "🛑 Global emergency stop executed. All users' bots paused.")
        else:
            await _send(update, "❌ Shutdown failed. Check logs.")

    else:
        await _send(update, "❌ Unknown confirmation action.")


# ── Unknown command ────────────────────────────────────────

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return
    await _send(update, "❌ Unknown command. Use /help for available commands.")


# ── Background tasks ───────────────────────────────────────

async def _daily_report_task(app: Application) -> None:
    global _last_daily_report
    try:
        while not _stop_event.is_set():
            now = datetime.now(timezone.utc)
            if now.hour == DAILY_REPORT_HOUR and now.minute >= DAILY_REPORT_MINUTE:
                today_key = now.strftime("%Y-%m-%d")
                if _last_daily_report != today_key:
                    _last_daily_report = today_key
                    report = get_daily_report()
                    if "error" not in report:
                        lines = [
                            f"📊 FUTURES Daily Report – {today_key}",
                            "────────────────────────────────────",
                            f"Active users: {report.get('active_users', 'N/A')}",
                            f"Trades today: {report.get('trades_today', 'N/A')}",
                            f"Net P&L today: ${report.get('pnl_today', 'N/A')}",
                            f"Win rate today: {report.get('win_rate', 'N/A')}",
                            f"Errors: {report.get('errors_today', 'N/A')}",
                        ]
                        msg = "\n".join(lines)
                        for aid in ALLOWED_IDS:
                            try:
                                await app.bot.send_message(chat_id=aid, text=msg)
                            except Exception as exc:
                                logger.warning("Failed to send daily report to %s: %s", aid, exc)
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        pass


async def _proactive_alerts_task(app: Application) -> None:
    try:
        while not _stop_event.is_set():
            now = datetime.now(timezone.utc)
            cutoff = (now - timedelta(minutes=5)).isoformat()

            try:
                issues = get_issues()
                for iss in issues:
                    iid = iss.get("id")
                    if iid in _sent_issue_ids:
                        continue
                    created = iss.get("created_at", "")
                    if created >= cutoff:
                        _sent_issue_ids.add(iid)
                        user_id = iss.get("user_id", "?")
                        title = iss.get("title", iss.get("subject", "?"))
                        desc = iss.get("description", iss.get("message", "?"))
                        screenshot = iss.get("screenshot_url", "")
                        lines = [
                            "🚨 New Support Ticket",
                            f"User: {user_id}",
                            f"Title: {title}",
                            f"Description: {desc}",
                        ]
                        if screenshot:
                            lines.append(f"Screenshot: {screenshot}")
                        msg = "\n".join(lines)
                        for aid in ALLOWED_IDS:
                            try:
                                await app.bot.send_message(chat_id=aid, text=msg)
                            except Exception as exc:
                                logger.warning("Failed to forward issue to %s: %s", aid, exc)
            except Exception as exc:
                logger.warning("Proactive alerts check error: %s", exc)

            await asyncio.sleep(POLL_INTERVAL)
    except asyncio.CancelledError:
        pass


# ── Bot factory ────────────────────────────────────────────

class TelegramAdminBot:
    def __init__(self, bot_state_ref: dict[str, Any] | None = None):
        if not BOT_TOKEN:
            raise RuntimeError("TELEGRAM_ADMIN_BOT_TOKEN not set")

        self.bot_state = bot_state_ref or {}
        self._app: Application | None = None
        self._tasks: list[asyncio.Task] = []
        self._running = False

    def _build_app(self) -> Application:
        app = Application.builder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("health", cmd_health))
        app.add_handler(CommandHandler("status", cmd_health))
        app.add_handler(CommandHandler("users", cmd_users))
        app.add_handler(CommandHandler("user", cmd_user))
        app.add_handler(CommandHandler("stop_user", cmd_stop_user))
        app.add_handler(CommandHandler("broadcast", cmd_broadcast))
        app.add_handler(CommandHandler("issues", cmd_issues))
        app.add_handler(CommandHandler("resolve", cmd_resolve))
        app.add_handler(CommandHandler("shutdown", cmd_shutdown))
        app.add_handler(CommandHandler("restart", cmd_restart))
        app.add_handler(CommandHandler("stats", cmd_stats))
        app.add_handler(CommandHandler("help", cmd_help))

        app.add_handler(MessageHandler(filters.Text(["CONFIRM"]), handle_confirm))
        app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

        return app

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        _stop_event.clear()

        self._app = self._build_app()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

        loop = asyncio.get_running_loop()
        self._tasks.append(loop.create_task(_daily_report_task(self._app)))
        self._tasks.append(loop.create_task(_proactive_alerts_task(self._app)))

        logger.info("Telegram admin bot started")

    async def stop(self) -> None:
        self._running = False
        _stop_event.set()

        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

        logger.info("Telegram admin bot stopped")


def create_admin_bot(bot_state_ref: dict[str, Any] | None = None) -> TelegramAdminBot:
    return TelegramAdminBot(bot_state_ref)
