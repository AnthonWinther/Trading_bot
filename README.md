# Trading Bot

A Python-based cryptocurrency paper trading bot that fetches live market data from Binance, generates trade signals using a momentum breakout strategy, and simulates realistic trade execution across multiple assets.

The project is currently in active development, with the backtesting engine complete and live paper trading in progress.

---

## Overview

The bot is structured in clear, separated layers:

- **Data ingestion** — fetches OHLCV candlestick data from the Binance public API with pagination support for arbitrary date ranges
- **Signal generation** — implements a momentum breakout strategy that identifies when price breaks above or below a recent high/low range
- **Trade simulation** — simulates buy and sell execution with realistic fee (0.1%) and slippage (0.05%) modeling
- **Backtesting engine** — walks through historical candles chronologically, simulating what the bot would have done at each point in time, with no lookahead bias
- **Multi-symbol support** — runs the full backtest across multiple trading pairs in a single execution

---

## Strategy: Momentum Breakout

The bot uses a momentum breakout strategy. For each candle, it looks at the highest and lowest closing prices over the previous 20 candles (the lookback window). If the current price breaks above that range, it generates a BUY signal. If it breaks below, it generates a SELL signal.

This strategy is designed to catch sustained directional moves — particularly effective in trending markets where price breakouts are followed by continued momentum.

**Why momentum breakout?**

Four strategies were backtested across 6 symbols over two market windows (bull and bear):

| Strategy | Bull market total P/L | Bear market total P/L |
|---|---|---|
| Momentum Breakout | **+1955 USDT** | **-715 USDT** |
| SMA Crossover | +1671 USDT | -1468 USDT |
| RSI | +465 USDT | -1998 USDT |
| MACD | -514 USDT | -1713 USDT |
| MACD + RSI | -331 USDT | -1578 USDT |

Momentum breakout was the strongest performer in the bull market and lost significantly less than any other strategy in the bear market.

---

## Backtesting Results

Tested across 6 symbols over a bull market window (Oct 2024 → Jan 2025):

| Symbol | P/L (USDT) | Trades |
|---|---|---|
| BTCUSDT | +168 | 71 |
| ETHUSDT | +32 | 75 |
| SOLUSDT | -74 | 75 |
| BNBUSDT | -17 | 63 |
| XRPUSDT | +1227 | 65 |
| ADAUSDT | +609 | 66 |

Starting capital: 1000 USDT per symbol. All results include 0.1% fee and 0.05% slippage per trade.

---

## Tech Stack

- **Python 3.9+**
- **requests** — Binance API data fetching
- **datetime / timezone** — UTC-aware timestamp handling

No external data science libraries (no pandas, no numpy) — all indicator and backtesting logic is implemented from scratch in plain Python.

---

## Project Structure

```
trading_bot/
│
├── bot.py          # Backtesting engine (complete)
└── live_bot.py     # Live paper trading loop (in progress)
```

---

## Configuration

All settings are defined at the top of `bot.py`:

```python
# Symbols to backtest
SYMBOLS = [
    {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT"},
    ...
]

INTERVAL        = "1h"           # Candle interval
START_DATE      = "2024-10-01"   # Backtest start date
END_DATE        = "2025-01-01"   # Backtest end date
BREAKOUT_PERIOD = 20             # Lookback window for breakout signal
FEE_RATE        = 0.001          # 0.1% per trade
SLIPPAGE_RATE   = 0.0005         # 0.05% per trade
STARTING_QUOTE_BALANCE = 1000.0  # Starting capital per symbol
```

---

## How to Run

**1. Clone the repository**
```bash
git clone https://github.com/AnthonWinther/Trading_bot.git
cd Trading_bot
```

**2. Create and activate a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install requests
```

**4. Run the backtester**
```bash
python3 bot.py
```

---

## Roadmap

- [x] Binance data ingestion with pagination
- [x] Candle formatting and close price extraction
- [x] Momentum breakout signal generation
- [x] Fee and slippage modeling
- [x] Multi-symbol backtesting engine
- [x] Fixed date window for reproducible results
- [ ] Live paper trading loop (scheduled execution every 10 minutes)
- [ ] Persistent state across runs (SQLite or JSON)
- [ ] Dockerization
- [ ] Cloud deployment
- [ ] Strategy performance monitoring and alerts

---

## Disclaimer

This project is for educational and portfolio purposes only. It does not constitute financial advice. No real money is used or at risk.