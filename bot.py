"""
Main Bot Orchestrator — the entry point.
Runs a scalping cycle every M15 candle close (minute 1, 16, 31, 46).
"""
import asyncio
import sys
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings
from core.mt5.connector import MT5Connector
from core.mt5.data_fetcher import DataFetcher
from core.analysis.mtf_analyzer import MTFAnalyzer
from core.analysis.signal_scorer import SignalScorer
from core.analysis.sr_detector import detect_sr_zones
from core.analysis.session_filter import SessionFilter
from core.analysis.news_filter import NewsFilter
from core.risk.sl_tp_manager import SLTPManager
from core.risk.position_sizer import PositionSizer
from core.risk.drawdown_guard import DrawdownGuard
from core.execution.order_manager import OrderManager
from notifications.telegram_notifier import TelegramNotifier


# ------------------------------------------------------------------
# Logging Setup
# ------------------------------------------------------------------
logger.remove()
logger.add(sys.stdout, colorize=True, format="{time:HH:mm:ss} | {level} | {message}")
logger.add("logs/bot_{time:YYYY-MM-DD}.log", rotation="1 day", retention="30 days")


# ------------------------------------------------------------------
# Component Instances
# ------------------------------------------------------------------
connector    = MT5Connector()
fetcher      = DataFetcher()
mtf_analyzer = MTFAnalyzer()
scorer       = SignalScorer()
session_filt = SessionFilter()
news_filt    = NewsFilter(
    suspend_before_min=settings.NEWS_FILTER and 30 or 0,
    suspend_after_min=settings.NEWS_FILTER and 30 or 0,
)
sl_tp_mgr    = SLTPManager(
    sl_multiplier=settings.ATR_SL_MULTIPLIER,
    min_rr=settings.MIN_RR,
)
pos_sizer    = PositionSizer()
dd_guard     = DrawdownGuard(
    max_daily_loss=settings.MAX_DAILY_LOSS,
    max_daily_trades=settings.MAX_DAILY_TRADES,
    max_consecutive_loss=settings.MAX_CONSECUTIVE_LOSS,
    cooldown_hours=settings.CONSECUTIVE_LOSS_COOLDOWN_HOURS,
    weekly_drawdown_limit=settings.WEEKLY_DRAWDOWN_LIMIT,
)
order_mgr    = OrderManager(magic=settings.MAGIC_NUMBER)
notifier     = TelegramNotifier(settings.TELEGRAM_TOKEN, settings.TELEGRAM_CHAT_ID)

# Track open positions managed by this bot
bot_positions: dict = {}  # ticket → {direction, entry, lot, tp1_hit, sl}


# ------------------------------------------------------------------
# Core Analysis Cycle
# ------------------------------------------------------------------
async def run_cycle():
    """Runs every M15 candle close."""
    logger.info(f"=== Cycle Start | {datetime.now().strftime('%H:%M:%S')} ===")

    # 1. Session check
    if settings.SESSION_FILTER and not session_filt.is_active():
        logger.info("Outside trading session — skipping")
        return

    # 2. News check
    if settings.NEWS_FILTER and news_filt.is_news_window():
        logger.warning(f"News blackout — clear in {news_filt.next_clear_time()}")
        return

    # 3. Account info & drawdown check
    account = connector.get_account_info()
    if account is None:
        logger.error("Cannot fetch account info — reconnecting...")
        connector.reconnect(settings.MT5_LOGIN, settings.MT5_PASSWORD, settings.MT5_SERVER)
        return

    suspended, reason = dd_guard.is_suspended(account.balance)
    if suspended:
        logger.warning(f"Trading suspended: {reason}")
        notifier.send_warning(f"Bot suspended: {reason}")
        return

    # 4. Spread check
    spread_pts = fetcher.get_spread_points(settings.SYMBOL)
    spread_ok  = spread_pts is not None and spread_pts <= settings.MAX_SPREAD_POINTS

    # 5. Fetch OHLCV all timeframes
    dfs = {}
    for tf in settings.TIMEFRAMES:
        df = fetcher.fetch_ohlcv(settings.SYMBOL, tf, count=300)
        if df is None:
            logger.error(f"Failed to fetch {tf} data — aborting cycle")
            return
        dfs[tf] = df

    # 6. MTF Analysis
    mtf = mtf_analyzer.analyze(dfs, settings.TIMEFRAMES)
    if not mtf.aligned:
        logger.info(f"MTF not aligned — no trade | {settings.TIMEFRAMES[0]}:{mtf.tf_master.overall_bias.value} {settings.TIMEFRAMES[1]}:{mtf.tf_confirm.overall_bias.value}")
        return

    # 7. S/R Detection (use Master TF for key levels)
    sr = detect_sr_zones(dfs[settings.TIMEFRAMES[0]])

    # 8. Score
    score = scorer.compute(
        mtf=mtf,
        sr=sr,
        spread_ok=spread_ok,
        session_active=session_filt.is_active(),
    )

    if score.size_factor == 0.0:
        logger.info(f"Score too low ({score.total}/100) — skipping")
        return

    # 9. Already have open position for this bot?
    open_positions = order_mgr.get_open_positions(settings.SYMBOL, settings.MAGIC_NUMBER)
    if open_positions:
        await _manage_open_positions(open_positions, dfs[settings.TIMEFRAMES[3]])
        return

    # 10. Compute SL/TP
    entry = mtf.entry_price
    atr   = mtf.tf_entry.atr_value
    levels = sl_tp_mgr.compute(mtf.direction, entry, atr)
    if not levels.valid:
        return

    # 11. Position sizing
    lot_full = pos_sizer.compute(
        balance=account.balance,
        risk_pct=settings.RISK_PER_TRADE,
        entry=entry,
        sl=levels.sl,
        size_factor=score.size_factor,
    )
    if lot_full is None:
        return

    # 12. Execute
    if settings.PAPER_TRADE:
        logger.success(
            f"[PAPER] {mtf.direction} {lot_full} lot @ {entry} | "
            f"SL:{levels.sl} TP1:{levels.tp1} TP2:{levels.tp2} | Score:{score.total}"
        )
        _paper_trade_log(mtf, levels, lot_full, score, account)
    else:
        result = order_mgr.place_entry(
            symbol=settings.SYMBOL,
            direction=mtf.direction,
            lot=lot_full,
            sl=levels.sl,
            tp=levels.tp1,  # TP1 first; update to TP2 after partial close
        )
        if result.success:
            bot_positions[result.ticket] = {
                "direction": mtf.direction,
                "entry": entry,
                "lot": lot_full,
                "tp1": levels.tp1,
                "tp2": levels.tp2,
                "sl": levels.sl,
                "tp1_hit": False,
                "atr": atr,
            }

    # 13. Notify
    notifier.send_entry(
        direction=mtf.direction,
        symbol=settings.SYMBOL,
        entry=entry,
        sl=levels.sl,
        tp1=levels.tp1,
        tp2=levels.tp2,
        lot=lot_full,
        score=score.total,
        risk_amount=account.balance * settings.RISK_PER_TRADE * score.size_factor,
        rr=levels.rr_tp2,
        session=session_filt.current_session(),
        confidence=score.grade,
        tf_master=settings.TIMEFRAMES[0],
        tf_confirm=settings.TIMEFRAMES[1],
        tf_setup=settings.TIMEFRAMES[2],
        tf_entry=settings.TIMEFRAMES[3],
        tf_master_bias=mtf.tf_master.overall_bias.value,
        tf_confirm_bias=mtf.tf_confirm.overall_bias.value,
        tf_setup_bias=mtf.tf_setup.overall_bias.value,
        tf_entry_pattern=mtf.tf_entry.pattern.description,
    )


# ------------------------------------------------------------------
# Position Management (Partial Close + Trailing)
# ------------------------------------------------------------------
async def _manage_open_positions(positions, df_entry):
    """Manage TP1 hit, breakeven, and trailing stop for open positions."""
    for pos in positions:
        ticket = pos.ticket
        meta   = bot_positions.get(ticket)
        if meta is None:
            continue

        direction = meta["direction"]
        current   = pos.price_current
        atr       = meta["atr"]

        # TP1 hit check
        if not meta["tp1_hit"]:
            tp1_hit = (
                (direction == "BUY"  and current >= meta["tp1"]) or
                (direction == "SELL" and current <= meta["tp1"])
            )
            if tp1_hit:
                # Close 50% of position
                close_lot = PositionSizer.partial_lot(meta["lot"], 0.50)
                ok = order_mgr.partial_close(ticket, settings.SYMBOL, close_lot, comment="TP1_50pct")
                if ok:
                    # Move SL to breakeven
                    be_sl = sl_tp_mgr.compute_breakeven_sl(direction, meta["entry"])
                    order_mgr.modify_sl(ticket, be_sl)
                    # Update TP to TP2
                    order_mgr.modify_tp(ticket, meta["tp2"])
                    meta["tp1_hit"] = True
                    meta["sl"] = be_sl
                    notifier.send_partial_close(
                        ticket=ticket, symbol=settings.SYMBOL,
                        direction=direction, closed_lot=close_lot,
                        close_price=current, pnl=0, note="TP1 hit → SL → BE"
                    )
                    logger.success(f"TP1 hit | Ticket:{ticket} → 50% closed, SL → BE")

        # Trailing stop for runner (after TP1)
        elif meta["tp1_hit"]:
            trail_sl = sl_tp_mgr.compute_trailing_sl(direction, current, atr)
            # Only tighten SL, never widen
            if direction == "BUY"  and trail_sl > meta["sl"]:
                order_mgr.modify_sl(ticket, trail_sl)
                meta["sl"] = trail_sl
            elif direction == "SELL" and trail_sl < meta["sl"]:
                order_mgr.modify_sl(ticket, trail_sl)
                meta["sl"] = trail_sl


def _paper_trade_log(mtf, levels, lot, score, account):
    """Log paper trade to file for later backtesting comparison."""
    with open("logs/paper_trades.csv", "a") as f:
        f.write(
            f"{datetime.now().isoformat()},{mtf.direction},{levels.sl_distance:.5f},"
            f"{levels.tp1},{levels.tp2},{levels.rr_tp2},{lot},{score.total},"
            f"{account.balance}\n"
        )


# ------------------------------------------------------------------
# Startup
# ------------------------------------------------------------------
async def main():
    logger.info("🤖 XAUUSD Scalping Bot Starting...")

    # Connect to MT5
    connected = connector.connect(
        login=settings.MT5_LOGIN,
        password=settings.MT5_PASSWORD,
        server=settings.MT5_SERVER,
    )
    if not connected:
        logger.error("Failed to connect to MT5. Exiting.")
        sys.exit(1)

    account = connector.get_account_info()
    logger.success(
        f"Account: {account.login} | Balance: {account.balance} {account.currency} | "
        f"Server: {account.server}"
    )
    notifier.send_warning(
        f"🤖 Bot started | {settings.SYMBOL} Scalper\n"
        f"Mode: {'📄 PAPER' if settings.PAPER_TRADE else '💰 LIVE'}\n"
        f"Balance: ${account.balance:.2f}"
    )

    # Schedule per 1-minute candle close
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_cycle, "cron", minute="*", second=5)
    scheduler.start()

    logger.success("✅ Scheduler started — waiting for 1M candle close")
    logger.info("Sessions: London 14:00-18:00 WIB | NY 19:00-23:00 WIB")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutting down...")
        connector.disconnect()
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
