# Trading Bot — XAUUSD Scalper (MT5 + Exness)

Professional automated scalping bot for **XAUUSD** using **MetaTrader 5** Python API.

## 📋 Requirements

- **OS**: Windows (required for MT5 Python library)
- **MT5**: MetaTrader 5 desktop installed + logged into Exness
- **Python**: 3.11+
- **Poetry**: `pip install poetry`

## 🚀 Quick Start

```bash
# 1. Install dependencies
poetry install

# 2. Configure environment
cp .env.example .env
# Edit .env with your MT5 login, password, server, Telegram token

# 3. Run in PAPER mode (safe — no real orders)
python bot.py

# 4. Run tests
pytest tests/ -v
```

## ⚙️ Configuration

Edit `.env`:

```env
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=Exness-MT5Trial     # Use Exness-MT5Real for live
PAPER_TRADE=true               # Set false for live execution
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Fine-tune strategy in `config/strategy_config.yaml`.

## 🏗️ Architecture

```
H4 → Master Bias
H1 → Momentum Confirmation
M30 → Setup Formation
M15 → Entry Trigger ⚡
```

**Signal Scoring (0-100):**
| Component | Weight |
|---|---|
| MTF Alignment | 30 |
| EMA Stack | 20 |
| MACD Direction | 15 |
| Candlestick Pattern | 15 |
| RSI Zone | 10 |
| ATR Filter | 5 |
| Spread/Session | 5 |

**Money Management:**

- Risk: 1% per trade
- TP1 (50% close): 1:1.0 → SL → Breakeven
- TP2 (30% close): 1:2.0
- TP3 (20%): Trailing 1x ATR
- Max 3 trades/day | 3% daily loss limit

**Sessions (WIB):**

- London: 14:00–18:00
- New York: 19:00–23:00

## 📁 Project Structure

```
config/           Strategy config and settings
core/mt5/         MT5 connection and data fetching
core/indicators/  Technical indicators (trend, momentum, volatility, patterns)
core/analysis/    MTF, scoring, S/R, session, news filter
core/risk/        SL/TP, position sizing, drawdown guard
core/execution/   Order management
notifications/    Telegram alerts
backtest/         Backtesting engine (WIP)
logs/             Rotating daily logs + paper trade CSV
tests/            Unit tests
```

## ⚠️ Disclaimers

> Trading carries significant risk. Past performance does not guarantee future results.
> Always test thoroughly on a demo account before going live.
# trading-bot-forex
