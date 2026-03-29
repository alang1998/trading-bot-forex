"""
Order Manager — MT5 order placement, partial close, SL modification,
and trailing stop management for XAUUSD scalping.
"""
import MetaTrader5 as mt5
from loguru import logger
from typing import Optional
from dataclasses import dataclass


@dataclass
class OrderResult:
    success: bool
    ticket: Optional[int]
    message: str


class OrderManager:
    """
    Wraps MT5 order operations for XAUUSD scalping.
    Supports: market entry, partial close, SL modification, trailing stop.
    """

    def __init__(self, magic: int = 20260328, deviation: int = 10):
        self._magic    = magic
        self._deviation = deviation

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------

    def place_entry(
        self,
        symbol: str,
        direction: str,   # "BUY" or "SELL"
        lot: float,
        sl: float,
        tp: float,        # Send TP1 on initial order
        comment: str = "scalp_entry",
    ) -> OrderResult:
        """Open market order."""
        price = self._get_price(symbol, direction)
        if price is None:
            return OrderResult(False, None, "Price fetch failed")

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        request = {
            "action":      mt5.TRADE_ACTION_DEAL,
            "symbol":      symbol,
            "volume":      lot,
            "type":        order_type,
            "price":       price,
            "sl":          sl,
            "tp":          tp,
            "deviation":   self._deviation,
            "magic":       self._magic,
            "comment":     comment,
            "type_time":   mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = result.comment if result else mt5.last_error()
            logger.error(f"Order failed: {err}")
            return OrderResult(False, None, str(err))

        logger.success(
            f"Order placed | Ticket:{result.order} {direction} {lot} lot @ {price} "
            f"SL:{sl} TP:{tp}"
        )
        return OrderResult(True, result.order, "OK")

    # ------------------------------------------------------------------
    # Modification
    # ------------------------------------------------------------------

    def modify_sl(self, ticket: int, new_sl: float) -> bool:
        """Modify stop loss (e.g. move to breakeven)."""
        position = self._get_position(ticket)
        if position is None:
            return False

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl":       new_sl,
            "tp":       position.tp,
        }
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            logger.info(f"SL modified | Ticket:{ticket} New SL:{new_sl}")
        else:
            logger.error(f"SL modify failed | Ticket:{ticket} Error:{mt5.last_error()}")
        return ok

    def modify_tp(self, ticket: int, new_tp: float) -> bool:
        """Modify take profit (e.g. update to TP2 after TP1 hit)."""
        position = self._get_position(ticket)
        if position is None:
            return False

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl":       position.sl,
            "tp":       new_tp,
        }
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            logger.info(f"TP modified | Ticket:{ticket} New TP:{new_tp}")
        return ok

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def partial_close(
        self,
        ticket: int,
        symbol: str,
        close_lot: float,
        comment: str = "partial_close",
    ) -> bool:
        """Close a fraction of an open position (e.g. 50% at TP1)."""
        position = self._get_position(ticket)
        if position is None:
            return False

        direction   = "SELL" if position.type == mt5.POSITION_TYPE_BUY else "BUY"
        close_price = self._get_price(symbol, direction)
        if close_price is None:
            return False

        close_type = mt5.ORDER_TYPE_SELL if direction == "SELL" else mt5.ORDER_TYPE_BUY

        request = {
            "action":    mt5.TRADE_ACTION_DEAL,
            "symbol":    symbol,
            "volume":    close_lot,
            "type":      close_type,
            "position":  ticket,
            "price":     close_price,
            "deviation": self._deviation,
            "magic":     self._magic,
            "comment":   comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            logger.success(f"Partial close | Ticket:{ticket} Lot:{close_lot}")
        else:
            logger.error(f"Partial close failed: {mt5.last_error()}")
        return ok

    def close_position(self, ticket: int, symbol: str) -> bool:
        """Close entire position."""
        position = self._get_position(ticket)
        if position is None:
            return False
        return self.partial_close(ticket, symbol, position.volume, comment="full_close")

    def close_all(self, symbol: str):
        """Emergency: close all open positions for symbol."""
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for p in positions:
                self.close_position(p.ticket, symbol)
            logger.warning(f"All positions closed for {symbol}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_open_positions(self, symbol: str, magic: Optional[int] = None):
        """Return open positions filtered by symbol and magic number."""
        positions = mt5.positions_get(symbol=symbol) or []
        if magic is not None:
            positions = [p for p in positions if p.magic == magic]
        return positions

    def _get_position(self, ticket: int):
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.warning(f"Position {ticket} not found")
            return None
        return positions[0]

    def _get_price(self, symbol: str, direction: str) -> Optional[float]:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return tick.ask if direction == "BUY" else tick.bid
