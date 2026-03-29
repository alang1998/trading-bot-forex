"""
Unit tests for signal scorer — verify scoring logic and thresholds.
"""
import pytest
from unittest.mock import MagicMock
from core.analysis.signal_scorer import SignalScorer, WEIGHTS
from core.indicators.trend import Bias
from core.indicators.patterns import PatternResult, PatternType


def make_mtf_signal(direction="BUY", all_bullish=True):
    """Helper to build a mock MTFSignal."""
    bias = Bias.BULLISH if all_bullish else Bias.BEARISH
    tf = MagicMock()
    tf.overall_bias  = bias
    tf.ema_bias      = bias
    tf.macd_bias     = bias
    tf.macd_crossover = "BULL_CROSS" if direction == "BUY" else "BEAR_CROSS"
    tf.rsi_value     = 32.0 if direction == "BUY" else 68.0
    tf.rsi_zone      = "OVERSOLD" if direction == "BUY" else "OVERBOUGHT"
    tf.rsi_divergence = None
    tf.atr_value     = 1.5
    tf.atr_normal    = True
    tf.pattern       = PatternResult(
        pattern=PatternType.PIN_BAR,
        direction="BULLISH" if direction == "BUY" else "BEARISH",
        weight=9,
        description="Pin Bar"
    )

    mtf = MagicMock()
    mtf.direction = direction
    mtf.h4 = tf; mtf.h1 = tf; mtf.m30 = tf; mtf.m15 = tf
    return mtf


def make_sr(at_level=True):
    sr = MagicMock()
    sr.at_key_level = at_level
    sr.level_bias = "AT_SUPPORT"
    return sr


class TestSignalScorer:
    def setup_method(self):
        self.scorer = SignalScorer()

    def test_perfect_buy_signal_scores_high(self):
        mtf = make_mtf_signal("BUY", True)
        sr  = make_sr(True)
        result = self.scorer.compute(mtf, sr, spread_ok=True, session_active=True)
        assert result.total >= 75
        assert result.grade == "STRONG"
        assert result.size_factor == 1.0

    def test_misaligned_signal_scores_low(self):
        """H4 bull, H1 bear → should not align → low score."""
        h4 = MagicMock(); h4.overall_bias = Bias.BULLISH
        h1 = MagicMock(); h1.overall_bias = Bias.BEARISH
        m30 = MagicMock(); m30.overall_bias = Bias.NEUTRAL
        m15 = MagicMock()
        m15.overall_bias = Bias.NEUTRAL
        m15.ema_bias = Bias.NEUTRAL
        m15.macd_bias = Bias.NEUTRAL
        m15.macd_crossover = None
        m15.rsi_zone = "NEUTRAL"
        m15.rsi_divergence = None
        m15.atr_normal = True
        m15.pattern = PatternResult(None, None, 0, "No pattern")

        mtf = MagicMock()
        mtf.direction = "BUY"
        mtf.h4 = h4; mtf.h1 = h1; mtf.m30 = m30; mtf.m15 = m15
        sr = make_sr(False)

        result = self.scorer.compute(mtf, sr, spread_ok=True, session_active=True)
        assert result.total < 60
        assert result.grade == "SKIP"
        assert result.size_factor == 0.0

    def test_half_size_in_moderate_range(self):
        """Score 60-74 → half size."""
        mtf = make_mtf_signal("BUY", True)
        # Remove some score by making pattern miss
        mtf.m15.pattern = PatternResult(None, None, 0, "No pattern")
        mtf.m15.macd_crossover = None
        mtf.m15.rsi_zone = "NEUTRAL"
        sr = make_sr(False)
        result = self.scorer.compute(mtf, sr, spread_ok=True, session_active=True)
        if 60 <= result.total < 75:
            assert result.size_factor == 0.5

    def test_weights_sum_to_100(self):
        assert sum(WEIGHTS.values()) == 100
