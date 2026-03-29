from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class BotSettings(BaseSettings):
    # MT5 Login
    MT5_LOGIN: int = Field(..., description="Elev8 account number")
    MT5_PASSWORD: str = Field(..., description="Elev8 account password")
    MT5_SERVER: str = Field("Elev8-Server", description="MT5 server name")

    # Trading
    SYMBOL: str = "XAUUSD"
    TIMEFRAMES: List[str] = ["M15", "M5", "M3", "M1"]
    RISK_PER_TRADE: float = 0.01       # 1% per trade
    MAX_DAILY_TRADES: int = 3
    MAX_DAILY_LOSS: float = 0.03       # 3% daily circuit breaker
    MIN_RR: float = 1.5                # Hard minimum R:R
    MAX_SPREAD_POINTS: int = 30        # Reject if spread > 30 points

    # Feature Flags
    PAPER_TRADE: bool = True
    SESSION_FILTER: bool = True
    NEWS_FILTER: bool = True

    # Indicator Params
    ATR_PERIOD: int = 14
    ATR_SL_MULTIPLIER: float = 1.2     # 1.2x ATR for SL
    ATR_MIN: float = 0.5               # Minimum ATR (avoid ranging)
    ATR_MAX: float = 3.0               # Maximum ATR (avoid news spike)
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 35.0
    RSI_OVERBOUGHT: float = 65.0
    EMA_FAST: int = 9
    EMA_MED: int = 21
    EMA_SLOW: int = 50
    EMA_TREND: int = 200

    # Scoring thresholds
    SCORE_FULL: int = 75               # Full size entry
    SCORE_HALF: int = 60               # Half size entry

    # Drawdown Protection
    MAX_CONSECUTIVE_LOSS: int = 3
    CONSECUTIVE_LOSS_COOLDOWN_HOURS: int = 2
    WEEKLY_DRAWDOWN_LIMIT: float = 0.06

    # Magic number (bot identifier in MT5)
    MAGIC_NUMBER: int = 20260328

    # Session times (WIB = UTC+8)
    LONDON_OPEN_HOUR_WIB: int = 14    # 14:00 WIB
    LONDON_CLOSE_HOUR_WIB: int = 18   # 18:00 WIB
    NY_OPEN_HOUR_WIB: int = 19        # 19:00 WIB
    NY_CLOSE_HOUR_WIB: int = 23       # 23:00 WIB

    # Telegram
    TELEGRAM_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./trading_bot.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = BotSettings()
