"""
Drawdown Guard — circuit breakers for daily loss, consecutive losses,
and weekly drawdown. Protects the account from catastrophic losses.
"""
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from loguru import logger
from dataclasses import dataclass, asdict
from typing import Optional


STATE_FILE = Path("./drawdown_state.json")


@dataclass
class DrawdownState:
    date: str           # YYYY-MM-DD
    daily_start_balance: float
    daily_pnl: float
    trades_today: int
    consecutive_losses: int
    cooldown_until: Optional[str]   # ISO datetime string
    weekly_start_balance: float
    week_start_date: str


class DrawdownGuard:
    """
    Monitors real-time account health and suspends bot when limits are hit.
    State is persisted to JSON so it survives bot restarts.
    """

    def __init__(
        self,
        max_daily_loss: float = 0.03,
        max_daily_trades: int = 3,
        max_consecutive_loss: int = 3,
        cooldown_hours: int = 2,
        weekly_drawdown_limit: float = 0.06,
    ):
        self._max_daily_loss      = max_daily_loss
        self._max_daily_trades    = max_daily_trades
        self._max_consec_loss     = max_consecutive_loss
        self._cooldown_hours      = cooldown_hours
        self._weekly_dd_limit     = weekly_drawdown_limit
        self._state               = self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_suspended(self, balance: float) -> tuple[bool, str]:
        """
        Returns (suspended: bool, reason: str).
        Call this before every trade cycle.
        """
        self._maybe_reset_daily(balance)

        # Cooldown window active?
        if self._state.cooldown_until:
            until = datetime.fromisoformat(self._state.cooldown_until)
            if datetime.now() < until:
                remaining = int((until - datetime.now()).total_seconds() // 60)
                return True, f"Cooldown active: {remaining} min remaining"
            else:
                self._state.cooldown_until = None
                self._save_state()

        # Daily loss limit
        daily_loss_pct = -self._state.daily_pnl / self._state.daily_start_balance
        if daily_loss_pct >= self._max_daily_loss:
            return True, f"Daily loss limit hit: {daily_loss_pct*100:.1f}% >= {self._max_daily_loss*100:.1f}%"

        # Max daily trades
        if self._state.trades_today >= self._max_daily_trades:
            return True, f"Max daily trades reached: {self._state.trades_today}"

        # Consecutive losses
        if self._state.consecutive_losses >= self._max_consec_loss:
            until = datetime.now() + timedelta(hours=self._cooldown_hours)
            self._state.cooldown_until = until.isoformat()
            self._save_state()
            return True, f"Consecutive losses: {self._state.consecutive_losses} → cooldown {self._cooldown_hours}h"

        # Weekly drawdown
        weekly_loss_pct = -( balance - self._state.weekly_start_balance) / self._state.weekly_start_balance
        if weekly_loss_pct >= self._weekly_dd_limit:
            return True, f"Weekly drawdown limit hit: {weekly_loss_pct*100:.1f}%"

        return False, ""

    def record_trade(self, pnl: float):
        """Call after every trade close."""
        self._state.daily_pnl += pnl
        self._state.trades_today += 1

        if pnl < 0:
            self._state.consecutive_losses += 1
        else:
            self._state.consecutive_losses = 0  # reset on win

        self._save_state()
        logger.info(
            f"Trade recorded | PnL:{pnl:+.2f} | Daily:{self._state.daily_pnl:+.2f} "
            f"| Trades:{self._state.trades_today} | ConsecLoss:{self._state.consecutive_losses}"
        )

    def get_stats(self) -> dict:
        return {
            "date": self._state.date,
            "daily_pnl": self._state.daily_pnl,
            "trades_today": self._state.trades_today,
            "consecutive_losses": self._state.consecutive_losses,
            "cooldown_until": self._state.cooldown_until,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_reset_daily(self, balance: float):
        today = str(date.today())
        if self._state.date != today:
            week_start = str(date.today() - timedelta(days=date.today().weekday()))
            if self._state.week_start_date != week_start:
                self._state.weekly_start_balance = balance
                self._state.week_start_date = week_start

            self._state.date = today
            self._state.daily_start_balance = balance
            self._state.daily_pnl = 0.0
            self._state.trades_today = 0
            self._state.consecutive_losses = 0
            self._state.cooldown_until = None
            self._save_state()
            logger.info(f"Daily state reset | New balance baseline: {balance}")

    def _load_state(self) -> DrawdownState:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                return DrawdownState(**data)
            except Exception:
                pass
        today = str(date.today())
        week_start = str(date.today() - timedelta(days=date.today().weekday()))
        return DrawdownState(
            date=today,
            daily_start_balance=0.0,
            daily_pnl=0.0,
            trades_today=0,
            consecutive_losses=0,
            cooldown_until=None,
            weekly_start_balance=0.0,
            week_start_date=week_start,
        )

    def _save_state(self):
        STATE_FILE.write_text(json.dumps(asdict(self._state), indent=2))
