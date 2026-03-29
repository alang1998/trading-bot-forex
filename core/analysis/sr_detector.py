"""
S/R Detector — identifies key support and resistance zones using
H4 swing highs/lows and classic Pivot Points.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SRLevel:
    price: float
    level_type: str     # "SUPPORT" | "RESISTANCE"
    source: str         # "SWING" | "PIVOT"
    strength: int       # 1-3 (how many times tested)


@dataclass
class SRResult:
    levels: List[SRLevel]
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    at_key_level: bool          # Price within threshold of any S/R
    level_bias: Optional[str]   # "AT_SUPPORT" | "AT_RESISTANCE"


def detect_sr_zones(
    df: pd.DataFrame,
    lookback: int = 50,
    proximity_pct: float = 0.002,  # 0.2% proximity to count as "at level"
) -> SRResult:
    """
    Detect support/resistance levels from swing highs/lows.
    Args:
        df: OHLCV DataFrame (typically H4)
        lookback: number of candles to scan for swings
        proximity_pct: % distance to consider price "at" a level
    """
    levels = _find_swing_levels(df.tail(lookback))
    levels += _compute_pivot_points(df.tail(2))

    price = df["close"].iloc[-1]

    supports = sorted(
        [l for l in levels if l.level_type == "SUPPORT" and l.price < price],
        key=lambda x: x.price, reverse=True
    )
    resistances = sorted(
        [l for l in levels if l.level_type == "RESISTANCE" and l.price > price],
        key=lambda x: x.price
    )

    nearest_support    = supports[0].price if supports else None
    nearest_resistance = resistances[0].price if resistances else None

    threshold = price * proximity_pct
    at_support    = nearest_support    and abs(price - nearest_support)    < threshold
    at_resistance = nearest_resistance and abs(price - nearest_resistance) < threshold

    at_key_level = bool(at_support or at_resistance)
    level_bias = None
    if at_support:
        level_bias = "AT_SUPPORT"
    elif at_resistance:
        level_bias = "AT_RESISTANCE"

    return SRResult(
        levels=levels,
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        at_key_level=at_key_level,
        level_bias=level_bias,
    )


def _find_swing_levels(df: pd.DataFrame, window: int = 5) -> List[SRLevel]:
    """Identify swing highs and lows using rolling window."""
    levels = []
    for i in range(window, len(df) - window):
        high = df["high"].iloc[i]
        low  = df["low"].iloc[i]

        is_swing_high = high == df["high"].iloc[i - window: i + window + 1].max()
        is_swing_low  = low  == df["low"].iloc[i - window: i + window + 1].min()

        if is_swing_high:
            levels.append(SRLevel(price=round(high, 5), level_type="RESISTANCE",
                                  source="SWING", strength=1))
        if is_swing_low:
            levels.append(SRLevel(price=round(low, 5), level_type="SUPPORT",
                                  source="SWING", strength=1))

    # Merge nearby levels (within 0.1%)
    return _merge_levels(levels, merge_pct=0.001)


def _compute_pivot_points(df: pd.DataFrame) -> List[SRLevel]:
    """Compute classic pivot points from previous day's H/L/C."""
    if len(df) < 1:
        return []
    prev = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    h, l, c = prev["high"], prev["low"], prev["close"]
    pp = (h + l + c) / 3
    r1 = (2 * pp) - l
    r2 = pp + (h - l)
    s1 = (2 * pp) - h
    s2 = pp - (h - l)

    return [
        SRLevel(price=round(pp, 5), level_type="SUPPORT",    source="PIVOT", strength=2),
        SRLevel(price=round(r1, 5), level_type="RESISTANCE", source="PIVOT", strength=2),
        SRLevel(price=round(r2, 5), level_type="RESISTANCE", source="PIVOT", strength=1),
        SRLevel(price=round(s1, 5), level_type="SUPPORT",    source="PIVOT", strength=2),
        SRLevel(price=round(s2, 5), level_type="SUPPORT",    source="PIVOT", strength=1),
    ]


def _merge_levels(levels: List[SRLevel], merge_pct: float = 0.001) -> List[SRLevel]:
    """Merge price levels that are within merge_pct of each other."""
    if not levels:
        return []
    sorted_levels = sorted(levels, key=lambda x: x.price)
    merged = [sorted_levels[0]]
    for lvl in sorted_levels[1:]:
        last = merged[-1]
        if abs(lvl.price - last.price) / last.price < merge_pct:
            # Merge: keep the one with higher strength
            if lvl.strength > last.strength:
                merged[-1] = lvl
            else:
                merged[-1].strength = max(last.strength, lvl.strength)
        else:
            merged.append(lvl)
    return merged
