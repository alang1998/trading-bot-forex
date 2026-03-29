"""
Trend Indicators — EMA stack, MACD, Ichimoku.
"""
import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Bias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class EMAResult:
    ema9: float
    ema21: float
    ema50: float
    ema200: float
    bias: Bias          # Based on EMA stack alignment
    price_vs_200: Bias  # Price above/below EMA200


@dataclass
class MACDResult:
    macd: float
    signal: float
    histogram: float
    bias: Bias           # MACD above/below zero
    crossover: Optional[str]  # "BULL_CROSS" | "BEAR_CROSS" | None


@dataclass
class IchimokuResult:
    tenkan: float
    kijun: float
    span_a: float
    span_b: float
    cloud_color: Bias   # Green=bullish, Red=bearish
    price_vs_cloud: Bias


def compute_emas(df: pd.DataFrame, fast=9, med=21, slow=50, trend=200) -> EMAResult:
    """Compute 4 EMAs and determine stack alignment."""
    close = df["close"]
    e9   = ta.ema(close, length=fast).iloc[-1]
    e21  = ta.ema(close, length=med).iloc[-1]
    e50  = ta.ema(close, length=slow).iloc[-1]
    e200 = ta.ema(close, length=trend).iloc[-1]
    price = close.iloc[-1]

    # Full bullish stack: price > ema9 > ema21 > ema50 > ema200
    if e9 > e21 > e50 > e200:
        bias = Bias.BULLISH
    elif e9 < e21 < e50 < e200:
        bias = Bias.BEARISH
    else:
        bias = Bias.NEUTRAL

    price_vs_200 = Bias.BULLISH if price > e200 else Bias.BEARISH

    return EMAResult(
        ema9=round(e9, 5),
        ema21=round(e21, 5),
        ema50=round(e50, 5),
        ema200=round(e200, 5),
        bias=bias,
        price_vs_200=price_vs_200,
    )


def compute_macd(
    df: pd.DataFrame, fast=12, slow=26, signal=9
) -> MACDResult:
    """Compute MACD and detect fresh crossovers."""
    macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    col_macd   = f"MACD_{fast}_{slow}_{signal}"
    col_signal = f"MACDs_{fast}_{slow}_{signal}"
    col_hist   = f"MACDh_{fast}_{slow}_{signal}"

    macd_val   = macd_df[col_macd].iloc[-1]
    signal_val = macd_df[col_signal].iloc[-1]
    hist_val   = macd_df[col_hist].iloc[-1]
    prev_hist  = macd_df[col_hist].iloc[-2]

    bias = Bias.BULLISH if hist_val > 0 else Bias.BEARISH

    crossover = None
    if prev_hist <= 0 < hist_val:
        crossover = "BULL_CROSS"
    elif prev_hist >= 0 > hist_val:
        crossover = "BEAR_CROSS"

    return MACDResult(
        macd=round(macd_val, 5),
        signal=round(signal_val, 5),
        histogram=round(hist_val, 5),
        bias=bias,
        crossover=crossover,
    )


def compute_ichimoku(df: pd.DataFrame) -> IchimokuResult:
    """Compute Ichimoku Cloud components."""
    ich = ta.ichimoku(df["high"], df["low"], df["close"])
    # pandas_ta returns tuple: (ichi, ichi_span) for lookahead
    ichi_df = ich[0]

    tenkan = ichi_df["ITS_9"].iloc[-1]
    kijun  = ichi_df["IKS_26"].iloc[-1]
    span_a = ichi_df["ISA_9"].iloc[-1]
    span_b = ichi_df["ISB_26"].iloc[-1]
    price  = df["close"].iloc[-1]

    cloud_color = Bias.BULLISH if span_a > span_b else Bias.BEARISH

    if price > max(span_a, span_b):
        price_vs_cloud = Bias.BULLISH
    elif price < min(span_a, span_b):
        price_vs_cloud = Bias.BEARISH
    else:
        price_vs_cloud = Bias.NEUTRAL

    return IchimokuResult(
        tenkan=round(tenkan, 5),
        kijun=round(kijun, 5),
        span_a=round(span_a, 5),
        span_b=round(span_b, 5),
        cloud_color=cloud_color,
        price_vs_cloud=price_vs_cloud,
    )
