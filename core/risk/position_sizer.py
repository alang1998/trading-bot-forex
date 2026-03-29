"""
Position Sizer — calculates lot size based on fixed % risk per trade.
Accounts for XAUUSD pip value and Elev8 lot constraints.
"""
import MetaTrader5 as mt5
from loguru import logger
from typing import Optional


class PositionSizer:
    """
    Fixed % risk position sizing for XAUUSD.
    Formula: lot = (balance × risk%) / (sl_distance_in_price × pip_value_per_lot)
    """

    XAUUSD_MIN_LOT  = 0.01
    XAUUSD_MAX_LOT  = 500.0
    XAUUSD_LOT_STEP = 0.01

    def compute(
        self,
        balance: float,
        risk_pct: float,
        entry: float,
        sl: float,
        symbol: str = "XAUUSD",
        size_factor: float = 1.0,  # 1.0 = full, 0.5 = half
    ) -> Optional[float]:
        """
        Compute lot size.
        Args:
            balance: account equity/balance in USD
            risk_pct: fraction to risk (e.g. 0.01 = 1%)
            entry: entry price
            sl: stop loss price
            size_factor: multiplier from signal scorer (1.0 or 0.5)
        Returns:
            lot size rounded to lot step, or None if calculation fails
        """
        sl_distance = abs(entry - sl)
        if sl_distance == 0:
            logger.error("SL distance is 0, cannot compute lot size")
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Cannot get symbol info for {symbol}")
            return None

        # pip value per 1.0 lot at current price
        # For XAUUSD on Elev8: 1 lot = 100 oz, tick = 0.01, tick_value ≈ $1
        pip_value_per_lot = symbol_info.trade_tick_value / symbol_info.trade_tick_size

        risk_amount = balance * risk_pct * size_factor
        raw_lots = risk_amount / (sl_distance * pip_value_per_lot)

        # Snap to lot step
        step = symbol_info.volume_step
        lots = round(raw_lots / step) * step
        lots = max(symbol_info.volume_min, min(symbol_info.volume_max, lots))
        lots = round(lots, 2)

        logger.info(
            f"Position Sizing | Balance:{balance:.2f} Risk:{risk_pct*100:.1f}% "
            f"SL dist:{sl_distance:.5f} → Lots:{lots} "
            f"(Risk Amount: ${risk_amount:.2f})"
        )

        return lots

    @staticmethod
    def partial_lot(total_lot: float, fraction: float) -> float:
        """Return lot for partial close (floored to 0.01 step)."""
        partial = total_lot * fraction
        return max(0.01, round(int(partial * 100) / 100, 2))
