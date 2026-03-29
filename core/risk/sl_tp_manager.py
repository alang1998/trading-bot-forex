"""
SL/TP Manager — ATR-based dynamic stop loss and take profit.
Implements partial closing strategy and trailing stop for the runner.
"""
from dataclasses import dataclass
from loguru import logger


@dataclass
class SLTPLevels:
    sl: float
    tp1: float      # 1:1 → 50% close + move SL to breakeven
    tp2: float      # 1:2 → 30% close
    tp3: float      # Trailing runner (20%)
    sl_distance: float
    rr_tp2: float   # Actual R:R to TP2
    valid: bool     # False if R:R < minimum


class SLTPManager:
    """
    Computes dynamic SL and tiered TP levels for XAUUSD scalping.
    SL formula: entry ± (ATR × multiplier)
    """

    def __init__(self, sl_multiplier: float = 1.2, min_rr: float = 1.5):
        self._sl_mult = sl_multiplier
        self._min_rr  = min_rr

    def compute(
        self,
        direction: str,     # "BUY" or "SELL"
        entry: float,
        atr: float,
    ) -> SLTPLevels:
        """
        Compute SL and 3-tier TP levels.
        TP1 = 1:1.0  (50% close, move SL to BE)
        TP2 = 1:2.0  (30% close)
        TP3 = trailing stop at 1x ATR from peak (20% runner)
        """
        sl_distance = round(atr * self._sl_mult, 5)

        if direction == "BUY":
            sl  = round(entry - sl_distance, 5)
            tp1 = round(entry + sl_distance * 1.0, 5)
            tp2 = round(entry + sl_distance * 2.0, 5)
            tp3 = round(entry + sl_distance * 3.0, 5)  # initial target for runner
        else:  # SELL
            sl  = round(entry + sl_distance, 5)
            tp1 = round(entry - sl_distance * 1.0, 5)
            tp2 = round(entry - sl_distance * 2.0, 5)
            tp3 = round(entry - sl_distance * 3.0, 5)

        rr_tp2 = round((abs(tp2 - entry)) / sl_distance, 2)
        valid  = rr_tp2 >= self._min_rr

        if not valid:
            logger.warning(
                f"Signal rejected: R:R={rr_tp2} < min={self._min_rr} | "
                f"ATR={atr} SL dist={sl_distance}"
            )

        logger.info(
            f"SL/TP | Dir:{direction} Entry:{entry} SL:{sl} "
            f"TP1:{tp1} TP2:{tp2} | R:R={rr_tp2} | Valid:{valid}"
        )

        return SLTPLevels(
            sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
            sl_distance=sl_distance,
            rr_tp2=rr_tp2,
            valid=valid,
        )

    def compute_trailing_sl(
        self,
        direction: str,
        peak_price: float,
        atr: float,
        trail_multiplier: float = 1.0,
    ) -> float:
        """
        Compute trailing stop level once TP1 is hit.
        Trailing = peak ± (ATR × trail_multiplier)
        """
        trail_dist = atr * trail_multiplier
        if direction == "BUY":
            return round(peak_price - trail_dist, 5)
        else:
            return round(peak_price + trail_dist, 5)

    def compute_breakeven_sl(
        self,
        direction: str,
        entry: float,
        offset_points: float = 0.10,  # 10 cents buffer above entry
    ) -> float:
        """Move SL to breakeven + small buffer after TP1 is hit."""
        if direction == "BUY":
            return round(entry + offset_points, 5)
        else:
            return round(entry - offset_points, 5)
