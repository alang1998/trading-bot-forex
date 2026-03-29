"""
Signal Scorer — computes a weighted confluence score (0-100)
from all indicator and analysis results.
"""
from dataclasses import dataclass
from typing import Dict
import pandas as pd
from loguru import logger

from core.analysis.mtf_analyzer import MTFSignal
from core.analysis.sr_detector import SRResult
from core.indicators.trend import Bias


# --- Weights (must sum to 100) ---
WEIGHTS = {
    "mtf_alignment":      30,   # H4+H1+M30+M15 alignment
    "ema_stack":          20,   # Full EMA alignment on entry TF
    "macd_direction":     15,   # MACD histogram direction + crossover
    "rsi_zone":           10,   # RSI in favorable zone
    "candlestick_pattern": 15,  # Pattern weight (normalized to 0-15)
    "atr_filter":          5,   # ATR in healthy range
    "spread_session":      5,   # Spread OK + active session
}


@dataclass
class ScoreResult:
    total: int
    breakdown: Dict[str, float]
    grade: str      # "STRONG" | "MODERATE" | "WEAK" | "SKIP"
    size_factor: float  # 1.0 = full size, 0.5 = half size, 0.0 = skip


class SignalScorer:
    """
    Aggregates signals into a single score.
    Entry only executed if score >= 60.
    """

    def compute(
        self,
        mtf: MTFSignal,
        sr: SRResult,
        spread_ok: bool,
        session_active: bool,
    ) -> ScoreResult:
        direction = mtf.direction  # "BUY" or "SELL"
        m15 = mtf.m15

        scores: Dict[str, float] = {}

        # 1. MTF Alignment (30 pts)
        biases = [mtf.h4.overall_bias, mtf.h1.overall_bias,
                  mtf.m30.overall_bias, mtf.m15.overall_bias]
        aligned_count = sum(1 for b in biases if (
            b == Bias.BULLISH if direction == "BUY" else b == Bias.BEARISH
        ))
        scores["mtf_alignment"] = (aligned_count / 4) * WEIGHTS["mtf_alignment"]

        # 2. EMA Stack M15 (20 pts)
        ema_aligned = (
            (m15.ema_bias == Bias.BULLISH and direction == "BUY") or
            (m15.ema_bias == Bias.BEARISH and direction == "SELL")
        )
        scores["ema_stack"] = WEIGHTS["ema_stack"] if ema_aligned else 0

        # 3. MACD (15 pts) — crossover in direction = full, bias only = half
        macd_full = (
            (m15.macd_crossover == "BULL_CROSS" and direction == "BUY") or
            (m15.macd_crossover == "BEAR_CROSS" and direction == "SELL")
        )
        macd_partial = (
            (m15.macd_bias == Bias.BULLISH and direction == "BUY") or
            (m15.macd_bias == Bias.BEARISH and direction == "SELL")
        )
        scores["macd_direction"] = (
            WEIGHTS["macd_direction"]       if macd_full else
            WEIGHTS["macd_direction"] * 0.5 if macd_partial else 0
        )

        # 4. RSI Zone (10 pts)
        rsi_ok = (
            (m15.rsi_zone == "OVERSOLD"  and direction == "BUY") or
            (m15.rsi_zone == "OVERBOUGHT" and direction == "SELL") or
            (m15.rsi_divergence == "BULLISH" and direction == "BUY") or
            (m15.rsi_divergence == "BEARISH" and direction == "SELL")
        )
        scores["rsi_zone"] = WEIGHTS["rsi_zone"] if rsi_ok else 0

        # 5. Candlestick Pattern (15 pts, normalized from 0-10 pattern weight)
        pattern = m15.pattern
        pat_dir_match = (
            (pattern.direction == "BULLISH" and direction == "BUY") or
            (pattern.direction == "BEARISH" and direction == "SELL")
        )
        pattern_score = (pattern.weight / 10) * WEIGHTS["candlestick_pattern"] if pat_dir_match else 0
        # Bonus: pattern at S/R level
        if pat_dir_match and sr.at_key_level:
            pattern_score = min(WEIGHTS["candlestick_pattern"], pattern_score * 1.2)
        scores["candlestick_pattern"] = round(pattern_score, 1)

        # 6. ATR Filter (5 pts)
        scores["atr_filter"] = WEIGHTS["atr_filter"] if m15.atr_normal else 0

        # 7. Spread + Session (5 pts)
        scores["spread_session"] = WEIGHTS["spread_session"] if (spread_ok and session_active) else 0

        total = int(sum(scores.values()))

        if total >= 75:
            grade = "STRONG"
            size_factor = 1.0
        elif total >= 60:
            grade = "MODERATE"
            size_factor = 0.5
        else:
            grade = "SKIP"
            size_factor = 0.0

        logger.info(f"Score: {total}/100 [{grade}] | {scores}")

        return ScoreResult(
            total=total,
            breakdown=scores,
            grade=grade,
            size_factor=size_factor,
        )
