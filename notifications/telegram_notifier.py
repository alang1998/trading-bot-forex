"""
Telegram Notifier — sends formatted alerts for entries, exits, and daily summaries.
"""
import asyncio
from datetime import datetime
from loguru import logger
from typing import Optional

try:
    from telegram import Bot
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class TelegramNotifier:
    """
    Sends trading alerts via Telegram Bot API.
    Falls back to log-only if token not configured.
    """

    def __init__(self, token: str, chat_id: str):
        self._token   = token
        self._chat_id = chat_id
        self._enabled = TELEGRAM_AVAILABLE and bool(token) and bool(chat_id)
        if not self._enabled:
            logger.warning("Telegram notifier disabled (no token/chat_id or library missing)")

    # ------------------------------------------------------------------
    # Alert Types
    # ------------------------------------------------------------------

    def send_entry(
        self,
        direction: str,
        symbol: str,
        entry: float,
        sl: float,
        tp1: float,
        tp2: float,
        lot: float,
        score: int,
        risk_amount: float,
        rr: float,
        session: str,
        confidence: str,
        tf_master: str,
        tf_confirm: str,
        tf_setup: str,
        tf_entry: str,
        tf_master_bias: str,
        tf_confirm_bias: str,
        tf_setup_bias: str,
        tf_entry_pattern: str,
    ):
        emoji = "📈" if direction == "BUY" else "📉"
        sl_pips = round(abs(entry - sl) * 10, 1)
        tp2_pips = round(abs(tp2 - entry) * 10, 1)

        msg = (
            f"{emoji} *SCALP SIGNAL — {symbol} {direction}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Entry  : `{entry:.2f}`\n"
            f"🛑 SL     : `{sl:.2f}`  (-{sl_pips} pips | 1.2x ATR)\n"
            f"✅ TP1    : `{tp1:.2f}`  (1:1 → BE)\n"
            f"✅ TP2    : `{tp2:.2f}`  (1:{rr:.1f})\n"
            f"🏃 TP3    : Trailing 1x ATR\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Score   : *{score}/100* [{confidence}]\n"
            f"⚡ Lot     : `{lot}`   💰 Risk: `${risk_amount:.2f}` (1%)\n"
            f"📐 R:R     : 1 : {rr:.1f}\n"
            f"⏱ TF      : {tf_master}{'🐂' if tf_master_bias=='BULLISH' else '🐻'} | "
            f"{tf_confirm}{'🐂' if tf_confirm_bias=='BULLISH' else '🐻'} | {tf_setup}📍 | {tf_entry}: {tf_entry_pattern}\n"
            f"🕐 Session : {session}\n"
            f"📰 News    : Clear ✅\n"
            f"🕒 Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self._send(msg)

    def send_partial_close(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        closed_lot: float,
        close_price: float,
        pnl: float,
        note: str = "TP1 hit",
    ):
        emoji = "💚" if pnl >= 0 else "🔴"
        msg = (
            f"{emoji} *PARTIAL CLOSE — {symbol}*\n"
            f"Ticket: `{ticket}` | {direction}\n"
            f"Closed: `{closed_lot}` lot @ `{close_price:.2f}`\n"
            f"PnL: `{pnl:+.2f} USD`\n"
            f"Note: {note}\n"
            f"SL → Breakeven ✅"
        )
        self._send(msg)

    def send_close(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        entry: float,
        close_price: float,
        lot: float,
        pnl: float,
        reason: str,
    ):
        emoji = "✅" if pnl >= 0 else "❌"
        pips = round(abs(close_price - entry) * 10, 1)
        result = "WIN" if pnl >= 0 else "LOSS"
        msg = (
            f"{emoji} *POSITION CLOSED — {symbol} {result}*\n"
            f"Ticket: `{ticket}` | {direction}\n"
            f"Entry: `{entry:.2f}` → Close: `{close_price:.2f}` ({pips} pips)\n"
            f"Lot: `{lot}` | PnL: `{pnl:+.2f} USD`\n"
            f"Reason: {reason}\n"
            f"🕒 {datetime.now().strftime('%H:%M:%S')}"
        )
        self._send(msg)

    def send_warning(self, message: str):
        self._send(f"⚠️ *WARNING*\n{message}")

    def send_daily_summary(
        self,
        date_str: str,
        trades: int,
        wins: int,
        losses: int,
        daily_pnl: float,
        balance: float,
    ):
        win_rate  = (wins / trades * 100) if trades > 0 else 0
        emoji = "📈" if daily_pnl >= 0 else "📉"
        msg = (
            f"{emoji} *DAILY SUMMARY — {date_str}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Trades: {trades}  |  W:{wins} / L:{losses}\n"
            f"Win Rate: {win_rate:.1f}%\n"
            f"Daily PnL: `{daily_pnl:+.2f} USD`\n"
            f"Balance: `{balance:.2f} USD`"
        )
        self._send(msg)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(self, text: str):
        logger.info(f"[TELEGRAM]\n{text}")
        if not self._enabled:
            return
        try:
            asyncio.get_event_loop().run_until_complete(self._async_send(text))
        except RuntimeError:
            # Already inside event loop
            asyncio.ensure_future(self._async_send(text))

    async def _async_send(self, text: str):
        try:
            bot = Bot(token=self._token)
            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")
