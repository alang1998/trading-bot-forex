"""
Unit tests for risk management: SL/TP levels and position sizing.
"""
import pytest
from core.risk.sl_tp_manager import SLTPManager
from core.risk.drawdown_guard import DrawdownGuard
import os


class TestSLTPManager:
    def setup_method(self):
        self.mgr = SLTPManager(sl_multiplier=1.2, min_rr=1.5)

    def test_buy_sl_below_entry(self):
        r = self.mgr.compute("BUY", entry=3000.0, atr=1.5)
        assert r.sl < 3000.0

    def test_sell_sl_above_entry(self):
        r = self.mgr.compute("SELL", entry=3000.0, atr=1.5)
        assert r.sl > 3000.0

    def test_buy_tp1_above_entry(self):
        r = self.mgr.compute("BUY", entry=3000.0, atr=1.5)
        assert r.tp1 > 3000.0
        assert r.tp2 > r.tp1

    def test_sell_tp1_below_entry(self):
        r = self.mgr.compute("SELL", entry=3000.0, atr=1.5)
        assert r.tp1 < 3000.0
        assert r.tp2 < r.tp1

    def test_rr_meets_minimum(self):
        r = self.mgr.compute("BUY", entry=3000.0, atr=1.5)
        assert r.rr_tp2 >= 1.5
        assert r.valid is True

    def test_breakeven_sl_correct(self):
        be = self.mgr.compute_breakeven_sl("BUY", entry=3000.0, offset_points=0.10)
        assert be > 3000.0  # Slightly above entry for BUY

    def test_trailing_tightens_on_peak(self):
        trail = self.mgr.compute_trailing_sl("BUY", peak_price=3010.0, atr=1.0)
        assert trail == pytest.approx(3009.0, abs=0.01)


class TestDrawdownGuard:
    def setup_method(self):
        # Use temp state file
        self.guard = DrawdownGuard(
            max_daily_loss=0.03,
            max_daily_trades=3,
            max_consecutive_loss=3,
            cooldown_hours=2,
            weekly_drawdown_limit=0.06,
        )
        # Reset state
        self.guard._state.daily_pnl = 0
        self.guard._state.trades_today = 0
        self.guard._state.consecutive_losses = 0
        self.guard._state.cooldown_until = None
        self.guard._state.daily_start_balance = 10000.0

    def test_not_suspended_fresh_start(self):
        suspended, _ = self.guard.is_suspended(10000.0)
        assert suspended is False

    def test_suspended_after_daily_loss(self):
        self.guard._state.daily_pnl = -350.0  # 3.5% of 10000
        suspended, reason = self.guard.is_suspended(10000.0)
        assert suspended is True
        assert "Daily loss" in reason

    def test_suspended_after_max_trades(self):
        self.guard._state.trades_today = 3
        suspended, reason = self.guard.is_suspended(10000.0)
        assert suspended is True
        assert "trades" in reason

    def test_consecutive_loss_triggers_cooldown(self):
        self.guard._state.consecutive_losses = 3
        suspended, reason = self.guard.is_suspended(10000.0)
        assert suspended is True
        assert "cooldown" in reason.lower() or "Consecutive" in reason

    def test_record_trade_updates_state(self):
        self.guard.record_trade(-50.0)
        assert self.guard._state.consecutive_losses == 1
        assert self.guard._state.daily_pnl == -50.0
        self.guard.record_trade(100.0)
        assert self.guard._state.consecutive_losses == 0  # reset on win
