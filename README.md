# Trading Bot

A Python-based cryptocurrency paper trading bot that fetches live market data from Binance, generates trade signals using a momentum breakout strategy, and simulates realistic trade execution across multiple assets.

The bot runs autonomously every ~10 minutes via GitHub Actions — no server required.

**[→ View live bot status](STATUS.md)**

---

## Overview

The bot is structured in clear, separated layers:

- **Data ingestion** — fetches OHLCV candlestick data from the Binance public API with pagination support for arbitrary date ranges
- **Signal generation** — implements a momentum breakout strategy that identifies when price breaks above or below a recent high/low range
- **Trade simulation** — simulates buy and sell execution with realistic fee (0.1%) and slippage (0.05%) modeling
- **Backtesting engine** — walks through historical candles chronologically, simulating what the bot would have done at each point in time, with no lookahead bias
- **Multi-symbol support** — runs the full backtest across multiple trading pairs in a single execution
- **Live paper trading** — runs autonomously every ~10 minutes via GitHub Actions, persisting portfolio state and publishing a live status dashboard between runs

---

## Strategy: Momentum Breakout

The bot uses a momentum breakout strategy. For each candle, it looks at the highest and lowest closing prices over the previous 20 candles (the lookback window). If the current price breaks above that range, it generates a BUY signal. If it breaks below, it generates a SELL signal.

This strategy is designed to catch sustained directional moves — particularly effective in trending markets where price breakouts are followed by continued momentum.

**Why momentum breakout?**

Five strategies were backtested across 6 symbols over two market windows (bull and bear):

| Strategy | Bull market total P/L | Bear market total P/L |
|---|---|---|
| **Momentum Breakout** | **+1955 USDT** | **-715 USDT** |
| SMA Crossover | +1671 USDT | -1468 USDT |
| RSI | +465 USDT | -1998 USDT |
| MACD + RSI | -331 USDT | -1578 USDT |
| MACD | -514 USDT | -1713 USDT |

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

## Live Trading

The live bot runs automatically every ~10 minutes via GitHub Actions at no cost. Each run:

1. Fetches the latest 100 candles from Binance for each symbol
2. Generates a momentum breakout signal
3. Explains in plain English why it is buying, selling, or holding
4. Simulates a buy or sell if the signal is actionable
5. Calculates current portfolio value and P/L
6. Saves the updated portfolio state to `live_state.json`
7. Publishes a live status dashboard to `STATUS.md`
8. Commits everything back to the repository

Current live symbols: BTCUSDT, ETHUSDT

**[→ View live status dashboard](STATUS.md)**

---

## Tech Stack

- **Python 3.9+**
- **requests** — Binance API data fetching
- **datetime / timezone** — UTC-aware timestamp handling
- **GitHub Actions** — free automated scheduling every ~10 minutes
- **JSON** — lightweight persistent state storage

No external data science libraries (no pandas, no numpy) — all indicator and backtesting logic is implemented from scratch in plain Python.

---

## Project Structure

```
Trading_bot/
│
├── bot.py                        # Backtesting engine
├── live_bot.py                   # Live paper trading bot
├── live_state.json               # Persistent portfolio state (auto-updated)
├── STATUS.md                     # Live status dashboard (auto-updated every ~10 min)
├── README.md
└── .github/
    └── workflows/
        └── live_bot.yml          # GitHub Actions scheduler
```

---

## Configuration

**Backtester (`bot.py`):**
```python
SYMBOLS = [
    {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT"},
    ...
]
INTERVAL        = "1h"           # Candle size
START_DATE      = "2024-10-01"   # Backtest start date
END_DATE        = "2025-01-01"   # Backtest end date
BREAKOUT_PERIOD = 20             # Lookback window for breakout signal
FEE_RATE        = 0.001          # 0.1% per trade
SLIPPAGE_RATE   = 0.0005         # 0.05% per trade
STARTING_QUOTE_BALANCE = 1000.0  # Starting capital per symbol
```

**Live bot (`live_bot.py`):**
```python
SYMBOLS = [
    {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT"},
    {"symbol": "ETHUSDT", "base": "ETH", "quote": "USDT"},
]
INTERVAL        = "1h"           # Candle size
CANDLE_LIMIT    = 100            # Latest candles to fetch per tick
BREAKOUT_PERIOD = 20
FEE_RATE        = 0.001
SLIPPAGE_RATE   = 0.0005
STARTING_QUOTE_BALANCE = 1000.0
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

**5. Run one live bot tick manually**
```bash
python3 live_bot.py
```

The live bot runs automatically every ~10 minutes via GitHub Actions — no manual intervention needed.

---

## Roadmap

- [x] Binance data ingestion with pagination
- [x] Candle formatting and close price extraction
- [x] Momentum breakout signal generation
- [x] Fee and slippage modeling
- [x] Multi-symbol backtesting engine
- [x] Fixed date window for reproducible results
- [x] Strategy comparison — 5 strategies tested across 6 symbols and 2 market windows
- [x] Live paper trading loop running every ~10 minutes
- [x] Persistent portfolio state across runs
- [x] Automated cloud deployment via GitHub Actions
- [x] Live status dashboard (STATUS.md) updated every tick
- [ ] Trade history log (CSV)
- [ ] Performance monitoring and alerts
- [ ] Sentiment analysis layer (Polymarket, X/Twitter)
- [ ] Stock market equivalent using Yahoo Finance

---

## Disclaimer

This project is for educational and portfolio purposes only. It does not constitute financial advice. No real money is used or at risk.