"""
Momentum Indicators — RSI, Stochastic, CCI + divergence detection.
"""
import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from .trend import Bias


@dataclass
class RSIResult:
    value: float
    zone: str           # "OVERSOLD" | "NEUTRAL" | "OVERBOUGHT"
    divergence: Optional[str]  # "BULLISH" | "BEARISH" | None


@dataclass
class StochasticResult:
    k: float
    d: float
    zone: str
    crossover: Optional[str]  # "BULL_CROSS" | "BEAR_CROSS" | None


@dataclass
class CCIResult:
    value: float
    bias: Bias


def compute_rsi(
    df: pd.DataFrame,
    period: int = 14,
    oversold: float = 35.0,
    overbought: float = 65.0,
) -> RSIResult:
    """Compute RSI and detect divergence over last 5 candles."""
    rsi_series = ta.rsi(df["close"], length=period)
    rsi_val = rsi_series.iloc[-1]

    if rsi_val <= oversold:
        zone = "OVERSOLD"
    elif rsi_val >= overbought:
        zone = "OVERBOUGHT"
    else:
        zone = "NEUTRAL"

    divergence = _detect_rsi_divergence(df["close"], rsi_series, lookback=5)

    return RSIResult(value=round(rsi_val, 2), zone=zone, divergence=divergence)


def _detect_rsi_divergence(
    price: pd.Series,
    rsi: pd.Series,
    lookback: int = 5,
) -> Optional[str]:
    """
    Detects bullish/bearish RSI divergence over recent candles.
    Bullish: price makes lower low, RSI makes higher low.
    Bearish: price makes higher high, RSI makes lower high.
    """
    price_window = price.iloc[-lookback:]
    rsi_window   = rsi.iloc[-lookback:]

    price_min_idx = price_window.idxmin()
    price_max_idx = price_window.idxmax()

    # Bullish divergence
    if (price_window.iloc[-1] < price_window.iloc[0] and
            rsi_window.iloc[-1] > rsi_window.iloc[0]):
        return "BULLISH"

    # Bearish divergence
    if (price_window.iloc[-1] > price_window.iloc[0] and
            rsi_window.iloc[-1] < rsi_window.iloc[0]):
        return "BEARISH"

    return None


def compute_stochastic(
    df: pd.DataFrame,
    k: int = 5,
    d: int = 3,
    smooth_k: int = 3,
    oversold: float = 20.0,
    overbought: float = 80.0,
) -> StochasticResult:
    """Compute fast Stochastic and detect crossovers in extreme zones."""
    stoch = ta.stoch(df["high"], df["low"], df["close"], k=k, d=d, smooth_k=smooth_k)
    k_col = f"STOCHk_{k}_{d}_{smooth_k}"
    d_col = f"STOCHd_{k}_{d}_{smooth_k}"

    k_val  = stoch[k_col].iloc[-1]
    d_val  = stoch[d_col].iloc[-1]
    k_prev = stoch[k_col].iloc[-2]
    d_prev = stoch[d_col].iloc[-2]

    if k_val <= oversold:
        zone = "OVERSOLD"
    elif k_val >= overbought:
        zone = "OVERBOUGHT"
    else:
        zone = "NEUTRAL"

    crossover = None
    # Bull cross: K crosses above D in oversold zone
    if k_prev < d_prev and k_val > d_val and k_val < 50:
        crossover = "BULL_CROSS"
    # Bear cross: K crosses below D in overbought zone
    elif k_prev > d_prev and k_val < d_val and k_val > 50:
        crossover = "BEAR_CROSS"

    return StochasticResult(
        k=round(k_val, 2),
        d=round(d_val, 2),
        zone=zone,
        crossover=crossover,
    )


def compute_cci(df: pd.DataFrame, period: int = 20) -> CCIResult:
    """Compute CCI. Values outside ±100 indicate strong momentum."""
    cci_series = ta.cci(df["high"], df["low"], df["close"], length=period)
    cci_val = cci_series.iloc[-1]
    bias = Bias.BULLISH if cci_val > 0 else Bias.BEARISH
    return CCIResult(value=round(cci_val, 2), bias=bias)
