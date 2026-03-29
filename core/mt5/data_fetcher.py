"""
Data Fetcher — fetches OHLCV and tick data from MT5.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger
from typing import Optional

TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
    "W1":  mt5.TIMEFRAME_W1,
}


class DataFetcher:
    """Fetches OHLCV candles and tick data from MT5."""

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 300,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candles from MT5.
        Returns DataFrame with columns: time, open, high, low, close, volume
        """
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            logger.error(f"Unknown timeframe: {timeframe}")
            return None

        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to fetch {symbol} {timeframe}: {mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        df = df[["open", "high", "low", "close", "tick_volume"]].rename(
            columns={"tick_volume": "volume"}
        )
        df = df.astype(float)
        logger.debug(f"Fetched {len(df)} candles | {symbol} {timeframe}")
        return df

    def fetch_ohlcv_range(
        self,
        symbol: str,
        timeframe: str,
        date_from: datetime,
        date_to: datetime,
    ) -> Optional[pd.DataFrame]:
        """Fetch historical OHLCV between two datetime objects (for backtest)."""
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            return None

        rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to fetch range {symbol} {timeframe}: {mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        df = df[["open", "high", "low", "close", "tick_volume"]].rename(
            columns={"tick_volume": "volume"}
        )
        return df.astype(float)

    def get_spread(self, symbol: str) -> Optional[float]:
        """Return current spread in price points (not pips)."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return round(tick.ask - tick.bid, 5)

    def get_spread_points(self, symbol: str) -> Optional[int]:
        """Return spread in broker points (comparable to MAX_SPREAD_POINTS)."""
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            return None
        spread_price = tick.ask - tick.bid
        return int(round(spread_price / info.point))

    def get_pip_value(self, symbol: str, lot: float = 1.0) -> Optional[float]:
        """Returns value of 1 pip movement for given lot size."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        # pip = 10 points for most symbols; XAUUSD point = 0.01
        return info.trade_tick_value * lot

    def latest_close(self, symbol: str, timeframe: str) -> Optional[float]:
        """Return the most recent closed candle's close price."""
        df = self.fetch_ohlcv(symbol, timeframe, count=2)
        if df is None or len(df) < 2:
            return None
        return df["close"].iloc[-2]  # -1 is still-open candle
