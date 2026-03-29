"""
Unit tests for indicator calculations.
These tests use synthetic OHLCV data to verify math correctness.
"""
import pandas as pd
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from core.indicators.trend import compute_emas, compute_macd, Bias
from core.indicators.momentum import compute_rsi, compute_stochastic
from core.indicators.volatility import compute_atr
from core.indicators.patterns import detect_pattern, PatternType


def make_trending_df(n=300, trend="up") -> pd.DataFrame:
    """Generate synthetic OHLCV with clear trend."""
    np.random.seed(42)
    base = 3000.0
    closes = []
    for i in range(n):
        noise = np.random.normal(0, 0.5)
        if trend == "up":
            closes.append(base + i * 0.5 + noise)
        else:
            closes.append(base - i * 0.5 + noise)

    df = pd.DataFrame({
        "open":   [c - 0.3 for c in closes],
        "high":   [c + 0.8 for c in closes],
        "low":    [c - 0.8 for c in closes],
        "close":  closes,
        "volume": [1000] * n,
    })
    return df


class TestEMAIndicator:
    def test_bullish_ema_stack_on_uptrend(self):
        df = make_trending_df(300, "up")
        result = compute_emas(df)
        assert result.bias == Bias.BULLISH

    def test_bearish_ema_stack_on_downtrend(self):
        df = make_trending_df(300, "down")
        result = compute_emas(df)
        assert result.bias == Bias.BEARISH

    def test_ema_values_are_finite(self):
        df = make_trending_df(300)
        result = compute_emas(df)
        assert all(np.isfinite(v) for v in [result.ema9, result.ema21, result.ema50, result.ema200])


class TestRSIIndicator:
    def test_oversold_on_sharp_drop(self):
        df = make_trending_df(300, "down")
        result = compute_rsi(df, oversold=35.0)
        # After prolonged downtrend RSI should be low
        assert result.value < 50

    def test_rsi_within_valid_range(self):
        df = make_trending_df(300)
        result = compute_rsi(df)
        assert 0 <= result.value <= 100

    def test_rsi_zone_labeling(self):
        df = make_trending_df(300, "up")
        result = compute_rsi(df, overbought=65.0)
        assert result.zone in ["OVERSOLD", "NEUTRAL", "OVERBOUGHT"]


class TestATRIndicator:
    def test_atr_is_positive(self):
        df = make_trending_df(300)
        result = compute_atr(df)
        assert result.value > 0

    def test_atr_in_normal_range(self):
        df = make_trending_df(300)
        result = compute_atr(df, atr_min=0.1, atr_max=100.0)
        assert result.is_normal is True

    def test_atr_spike_flagged(self):
        df = make_trending_df(300)
        result = compute_atr(df, atr_min=100.0, atr_max=200.0)
        assert result.is_normal is False


class TestPatternDetector:
    def test_no_pattern_on_neutral_candles(self):
        """Small doji-like candles should not trigger major patterns."""
        closes = [3000.0 + i * 0.01 for i in range(300)]
        df = pd.DataFrame({
            "open":   [c - 0.005 for c in closes],
            "high":   [c + 0.01  for c in closes],
            "low":    [c - 0.01  for c in closes],
            "close":  closes,
            "volume": [1000] * 300,
        })
        result = detect_pattern(df)
        # Should find a Doji at most
        assert result.pattern in [None, PatternType.DOJI]

    def test_bullish_engulfing_detected(self):
        """Craft explicit bullish engulfing last 2 candles."""
        closes = [3000.0] * 298 + [2995.0, 3005.0]  # prev bearish, last bullish
        opens  = [3000.0] * 298 + [3000.0, 2993.0]
        highs  = [c + 1 for c in closes]
        lows   = [c - 1 for c in closes]
        df = pd.DataFrame({
            "open": opens, "high": highs, "low": lows,
            "close": closes, "volume": [1000] * 300,
        })
        result = detect_pattern(df)
        assert result.pattern == PatternType.ENGULFING
        assert result.direction == "BULLISH"
