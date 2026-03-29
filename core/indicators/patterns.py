"""
Candlestick Pattern Detector — Pin Bar, Engulfing, Inside Bar, Doji, Hammer,
Shooting Star, Morning/Evening Star. Designed for XAUUSD scalping.
"""
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PatternType(str, Enum):
    PIN_BAR = "PIN_BAR"
    ENGULFING = "ENGULFING"
    INSIDE_BAR = "INSIDE_BAR"
    HAMMER = "HAMMER"
    SHOOTING_STAR = "SHOOTING_STAR"
    DOJI = "DOJI"
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"


# Pattern weights for scoring (0-10)
PATTERN_WEIGHTS = {
    PatternType.PIN_BAR:       9,
    PatternType.ENGULFING:     8,
    PatternType.INSIDE_BAR:    7,
    PatternType.HAMMER:        7,
    PatternType.SHOOTING_STAR: 7,
    PatternType.MORNING_STAR:  8,
    PatternType.EVENING_STAR:  8,
    PatternType.DOJI:          5,
}


@dataclass
class PatternResult:
    pattern: Optional[PatternType]
    direction: Optional[str]   # "BULLISH" | "BEARISH"
    weight: int                # 0-10
    description: str


def detect_pattern(df: pd.DataFrame) -> PatternResult:
    """
    Detect the most significant pattern in the last completed candle (index -2).
    Returns the pattern with the highest weight if multiple detected.
    """
    # Use last completed candle (-2) to avoid lookahead on open candle
    c = df.iloc[-2]
    prev = df.iloc[-3]

    body = abs(c["close"] - c["open"])
    candle_range = c["high"] - c["low"]
    body_pct = body / candle_range if candle_range > 0 else 0

    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]

    is_bull_candle = c["close"] > c["open"]
    is_bear_candle = c["close"] < c["open"]

    detected: list[PatternResult] = []

    # --- PIN BAR ---
    # Long wick (> 60% of range) with small body at one end
    if lower_wick > candle_range * 0.6 and body_pct < 0.35:
        detected.append(PatternResult(
            pattern=PatternType.PIN_BAR, direction="BULLISH",
            weight=PATTERN_WEIGHTS[PatternType.PIN_BAR],
            description="Bullish Pin Bar — long lower wick"
        ))
    elif upper_wick > candle_range * 0.6 and body_pct < 0.35:
        detected.append(PatternResult(
            pattern=PatternType.PIN_BAR, direction="BEARISH",
            weight=PATTERN_WEIGHTS[PatternType.PIN_BAR],
            description="Bearish Pin Bar — long upper wick"
        ))

    # --- ENGULFING ---
    prev_body = abs(prev["close"] - prev["open"])
    if (is_bull_candle and prev["close"] < prev["open"]  # prev bearish
            and c["close"] > prev["open"] and c["open"] < prev["close"]
            and body > prev_body):
        detected.append(PatternResult(
            pattern=PatternType.ENGULFING, direction="BULLISH",
            weight=PATTERN_WEIGHTS[PatternType.ENGULFING],
            description="Bullish Engulfing"
        ))
    elif (is_bear_candle and prev["close"] > prev["open"]  # prev bullish
            and c["close"] < prev["open"] and c["open"] > prev["close"]
            and body > prev_body):
        detected.append(PatternResult(
            pattern=PatternType.ENGULFING, direction="BEARISH",
            weight=PATTERN_WEIGHTS[PatternType.ENGULFING],
            description="Bearish Engulfing"
        ))

    # --- INSIDE BAR ---
    if c["high"] < prev["high"] and c["low"] > prev["low"]:
        direction = "BULLISH" if is_bull_candle else "BEARISH"
        detected.append(PatternResult(
            pattern=PatternType.INSIDE_BAR, direction=direction,
            weight=PATTERN_WEIGHTS[PatternType.INSIDE_BAR],
            description=f"Inside Bar ({direction})"
        ))

    # --- HAMMER ---
    if (is_bull_candle and lower_wick > body * 2
            and upper_wick < body * 0.5):
        detected.append(PatternResult(
            pattern=PatternType.HAMMER, direction="BULLISH",
            weight=PATTERN_WEIGHTS[PatternType.HAMMER],
            description="Hammer"
        ))

    # --- SHOOTING STAR ---
    if (is_bear_candle and upper_wick > body * 2
            and lower_wick < body * 0.5):
        detected.append(PatternResult(
            pattern=PatternType.SHOOTING_STAR, direction="BEARISH",
            weight=PATTERN_WEIGHTS[PatternType.SHOOTING_STAR],
            description="Shooting Star"
        ))

    # --- DOJI ---
    if body_pct < 0.05 and candle_range > 0:
        detected.append(PatternResult(
            pattern=PatternType.DOJI, direction=None,
            weight=PATTERN_WEIGHTS[PatternType.DOJI],
            description="Doji — indecision"
        ))

    # Return highest-weight pattern, or no_pattern if none
    if not detected:
        return PatternResult(pattern=None, direction=None, weight=0, description="No significant pattern")

    return max(detected, key=lambda p: p.weight)
