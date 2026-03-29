"""
Volatility Indicators — ATR, Bollinger Bands, Keltner Channel.
"""
import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass
from typing import Optional


@dataclass
class ATRResult:
    value: float
    is_normal: bool     # True if within min/max thresholds (filter ranging/spikes)


@dataclass
class BollingerResult:
    upper: float
    mid: float
    lower: float
    bandwidth: float
    squeeze: bool       # Low bandwidth = potential breakout
    price_position: str # "ABOVE_UPPER" | "BELOW_LOWER" | "INSIDE"


@dataclass
class KeltnerResult:
    upper: float
    mid: float
    lower: float
    price_position: str


@dataclass
class VolatilityResult:
    atr: ATRResult
    bollinger: BollingerResult
    keltner: KeltnerResult
    bb_kc_squeeze: bool  # BB inside KC = powerful squeeze signal


def compute_atr(
    df: pd.DataFrame,
    period: int = 14,
    atr_min: float = 0.5,
    atr_max: float = 3.0,
) -> ATRResult:
    """Compute ATR and validate it's within healthy trading range."""
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=period)
    atr_val = atr_series.iloc[-1]
    is_normal = atr_min <= atr_val <= atr_max
    return ATRResult(value=round(atr_val, 5), is_normal=is_normal)


def compute_bollinger(
    df: pd.DataFrame,
    period: int = 20,
    std: float = 2.0,
    squeeze_threshold: float = 0.002,
) -> BollingerResult:
    """Compute Bollinger Bands and detect squeeze (low bandwidth)."""
    bb = ta.bbands(df["close"], length=period, std=std)
    upper = bb[f"BBU_{period}_{std}"].iloc[-1]
    mid   = bb[f"BBM_{period}_{std}"].iloc[-1]
    lower = bb[f"BBL_{period}_{std}"].iloc[-1]
    bw    = bb[f"BBB_{period}_{std}"].iloc[-1]  # bandwidth %
    price = df["close"].iloc[-1]

    squeeze = bw < squeeze_threshold * 100

    if price > upper:
        position = "ABOVE_UPPER"
    elif price < lower:
        position = "BELOW_LOWER"
    else:
        position = "INSIDE"

    return BollingerResult(
        upper=round(upper, 5),
        mid=round(mid, 5),
        lower=round(lower, 5),
        bandwidth=round(bw, 4),
        squeeze=squeeze,
        price_position=position,
    )


def compute_keltner(
    df: pd.DataFrame,
    period: int = 20,
    atr_period: int = 10,
    multiplier: float = 1.5,
) -> KeltnerResult:
    """Compute Keltner Channel."""
    kc = ta.kc(df["high"], df["low"], df["close"], length=period, scalar=multiplier)
    upper = kc[f"KCUe_{period}_{multiplier}"].iloc[-1]
    mid   = kc[f"KCBe_{period}_{multiplier}"].iloc[-1]
    lower = kc[f"KCLe_{period}_{multiplier}"].iloc[-1]
    price = df["close"].iloc[-1]

    if price > upper:
        position = "ABOVE_UPPER"
    elif price < lower:
        position = "BELOW_LOWER"
    else:
        position = "INSIDE"

    return KeltnerResult(
        upper=round(upper, 5),
        mid=round(mid, 5),
        lower=round(lower, 5),
        price_position=position,
    )


def compute_volatility(df: pd.DataFrame, atr_min=0.5, atr_max=3.0) -> VolatilityResult:
    """Compute all volatility indicators and detect BB/KC squeeze."""
    atr = compute_atr(df, atr_min=atr_min, atr_max=atr_max)
    bb  = compute_bollinger(df)
    kc  = compute_keltner(df)

    # Classic squeeze: BB upper < KC upper AND BB lower > KC lower
    bb_kc_squeeze = (bb.upper < kc.upper) and (bb.lower > kc.lower)

    return VolatilityResult(atr=atr, bollinger=bb, keltner=kc, bb_kc_squeeze=bb_kc_squeeze)
