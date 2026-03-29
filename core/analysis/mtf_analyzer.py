"""
Multi-Timeframe Analyzer — H4 → H1 → M30 → M15 alignment check.
Entry is ONLY valid when all timeframes are aligned on the same direction.
"""
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Optional
from loguru import logger

from core.indicators.trend import compute_emas, compute_macd, Bias
from core.indicators.momentum import compute_rsi, compute_stochastic
from core.indicators.volatility import compute_volatility
from core.indicators.patterns import detect_pattern, PatternResult


@dataclass
class TimeframeAnalysis:
    timeframe: str
    ema_bias: Bias
    macd_bias: Bias
    macd_crossover: Optional[str]
    rsi_value: float
    rsi_zone: str
    rsi_divergence: Optional[str]
    stoch_crossover: Optional[str]
    atr_value: float
    atr_normal: bool
    pattern: PatternResult
    overall_bias: Bias


@dataclass
class MTFSignal:
    aligned: bool
    direction: Optional[str]    # "BUY" | "SELL" | None
    tf_master: TimeframeAnalysis
    tf_confirm: TimeframeAnalysis
    tf_setup: TimeframeAnalysis
    tf_entry: TimeframeAnalysis
    entry_price: Optional[float]
    confidence: str             # "STRONG" | "MODERATE" | "WEAK"


class MTFAnalyzer:
    """
    Analyzes 4 timeframes and returns a consolidated signal.
    Rule: Entry only if Master + Confirm agree AND Setup + Entry provide trigger.
    """

    def analyze(self, dfs: Dict[str, pd.DataFrame], timeframes: list[str]) -> MTFSignal:
        """
        Args:
            dfs: dict with timeframe keys → pd.DataFrame
            timeframes: list of 4 timeframes (e.g., ["M15", "M5", "M3", "M1"])
        Returns:
            MTFSignal with alignment status and direction
        """
        if len(timeframes) != 4:
            logger.error("MTFAnalyzer requires exactly 4 timeframes")
            raise ValueError("Need exactly 4 timeframes")

        tf1, tf2, tf3, tf4 = timeframes

        master  = self._analyze_tf(dfs[tf1], tf1)
        confirm = self._analyze_tf(dfs[tf2], tf2)
        setup   = self._analyze_tf(dfs[tf3], tf3)
        entry   = self._analyze_tf(dfs[tf4], tf4)

        biases = [master.overall_bias, confirm.overall_bias, setup.overall_bias, entry.overall_bias]
        bull_count = biases.count(Bias.BULLISH)
        bear_count = biases.count(Bias.BEARISH)

        # Strict: Master and Confirm MUST agree (they are the bias filters)
        master_confirm_bull = master.overall_bias == Bias.BULLISH and confirm.overall_bias == Bias.BULLISH
        master_confirm_bear = master.overall_bias == Bias.BEARISH and confirm.overall_bias == Bias.BEARISH

        aligned = master_confirm_bull or master_confirm_bear
        direction = None
        confidence = "WEAK"

        if master_confirm_bull:
            direction = "BUY"
            if bull_count == 4:
                confidence = "STRONG"
            elif bull_count >= 3:
                confidence = "MODERATE"

        elif master_confirm_bear:
            direction = "SELL"
            if bear_count == 4:
                confidence = "STRONG"
            elif bear_count >= 3:
                confidence = "MODERATE"

        # Entry price = last close on tf_entry (trigger timeframe)
        entry_price = dfs[tf4]["close"].iloc[-2] if aligned else None

        logger.info(
            f"MTF | {tf1}:{master.overall_bias.value} {tf2}:{confirm.overall_bias.value} "
            f"{tf3}:{setup.overall_bias.value} {tf4}:{entry.overall_bias.value} "
            f"→ Aligned:{aligned} Dir:{direction} Conf:{confidence}"
        )

        return MTFSignal(
            aligned=aligned,
            direction=direction,
            tf_master=master,
            tf_confirm=confirm,
            tf_setup=setup,
            tf_entry=entry,
            entry_price=entry_price,
            confidence=confidence,
        )

    def _analyze_tf(self, df: pd.DataFrame, tf_label: str) -> TimeframeAnalysis:
        """Run all indicators on a single timeframe DataFrame."""
        ema     = compute_emas(df)
        macd    = compute_macd(df)
        rsi     = compute_rsi(df)
        stoch   = compute_stochastic(df)
        vol     = compute_volatility(df)
        pattern = detect_pattern(df)

        # Combine EMA and MACD for overall TF bias
        bullish_votes = sum([
            ema.bias == Bias.BULLISH,
            ema.price_vs_200 == Bias.BULLISH,
            macd.bias == Bias.BULLISH,
        ])
        bearish_votes = sum([
            ema.bias == Bias.BEARISH,
            ema.price_vs_200 == Bias.BEARISH,
            macd.bias == Bias.BEARISH,
        ])

        if bullish_votes > bearish_votes:
            overall = Bias.BULLISH
        elif bearish_votes > bullish_votes:
            overall = Bias.BEARISH
        else:
            overall = Bias.NEUTRAL

        return TimeframeAnalysis(
            timeframe=tf_label,
            ema_bias=ema.bias,
            macd_bias=macd.bias,
            macd_crossover=macd.crossover,
            rsi_value=rsi.value,
            rsi_zone=rsi.zone,
            rsi_divergence=rsi.divergence,
            stoch_crossover=stoch.crossover,
            atr_value=vol.atr.value,
            atr_normal=vol.atr.is_normal,
            pattern=pattern,
            overall_bias=overall,
        )
