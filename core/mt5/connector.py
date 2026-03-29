"""
MT5 Connector — handles initialization, login, and shutdown.
Must run on Windows with MetaTrader5 desktop app installed and running.
"""
import MetaTrader5 as mt5
from loguru import logger
from dataclasses import dataclass
from typing import Optional


@dataclass
class AccountInfo:
    login: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    currency: str
    leverage: int
    server: str


class MT5Connector:
    """Wrapper around MetaTrader5 Python library for Elev8."""

    def __init__(self):
        self._connected = False

    def connect(self, login: int, password: str, server: str) -> bool:
        """Initialize and login to MT5."""
        if not mt5.initialize():
            logger.error(f"MT5 initialize failed: {mt5.last_error()}")
            return False

        authorized = mt5.login(login, password=password, server=server)
        if not authorized:
            logger.error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        info = mt5.account_info()
        self._connected = True
        logger.success(
            f"Connected to MT5 | Login: {info.login} | Server: {info.server} | "
            f"Balance: {info.balance} {info.currency}"
        )
        return True

    def disconnect(self):
        """Safely shutdown MT5 connection."""
        mt5.shutdown()
        self._connected = False
        logger.info("MT5 connection closed.")

    def is_connected(self) -> bool:
        """Check if terminal is still responsive."""
        if not self._connected:
            return False
        return mt5.terminal_info() is not None

    def reconnect(self, login: int, password: str, server: str) -> bool:
        """Attempt to reconnect if connection is lost."""
        logger.warning("Attempting MT5 reconnect...")
        self.disconnect()
        return self.connect(login, password, server)

    def get_account_info(self) -> Optional[AccountInfo]:
        """Fetch current account snapshot."""
        info = mt5.account_info()
        if info is None:
            logger.error(f"Failed to get account info: {mt5.last_error()}")
            return None
        return AccountInfo(
            login=info.login,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level,
            currency=info.currency,
            leverage=info.leverage,
            server=info.server,
        )

    def get_symbol_info(self, symbol: str):
        """Get symbol metadata (tick size, lot step, min lot, etc.)."""
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Symbol {symbol} not found: {mt5.last_error()}")
        return info

    def get_current_price(self, symbol: str) -> Optional[dict]:
        """Get current bid/ask and spread."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": round(tick.ask - tick.bid, 2),
            "time": tick.time,
        }
