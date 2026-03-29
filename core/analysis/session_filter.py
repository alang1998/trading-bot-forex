"""
Session Filter — restricts trading to London and New York sessions (WIB).
XAUUSD has best volume and tightest spreads during these windows.
"""
from datetime import datetime
import pytz
from loguru import logger


WIB = pytz.timezone("Asia/Jakarta")


class SessionFilter:
    """
    London Session : 14:00 – 18:00 WIB
    New York Session: 19:00 – 23:00 WIB
    Kill zone (best): 19:00 – 21:00 WIB (London/NY overlap)
    Asia Session   : SKIP (low volume on XAUUSD)
    """

    SESSIONS = [
        {"name": "London",   "open": 14, "close": 18},
        {"name": "New York", "open": 19, "close": 23},
    ]

    def is_active(self) -> bool:
        """Return True if current WIB time is within any active session."""
        now_wib = datetime.now(WIB)
        hour    = now_wib.hour

        for session in self.SESSIONS:
            if session["open"] <= hour < session["close"]:
                logger.debug(f"Active session: {session['name']} ({hour}:xx WIB)")
                return True

        logger.debug(f"No active session at {hour}:xx WIB — skipping cycle")
        return False

    def current_session(self) -> str:
        """Return name of current session, or 'CLOSED'."""
        now_wib = datetime.now(WIB)
        hour    = now_wib.hour

        for session in self.SESSIONS:
            if session["open"] <= hour < session["close"]:
                return session["name"]
        return "CLOSED"

    def is_kill_zone(self) -> bool:
        """Return True during London/NY overlap (highest volatility)."""
        hour = datetime.now(WIB).hour
        return 19 <= hour < 21
