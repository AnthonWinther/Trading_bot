import requests
import json
import os
from datetime import datetime, timezone

BASE_URL = "https://data-api.binance.vision"

# =============================================================================
# CONFIGURATION
# =============================================================================

# Symbols to trade live
SYMBOLS = [
    {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT"},
    {"symbol": "ETHUSDT", "base": "ETH", "quote": "USDT"},
]

INTERVAL        = "1h"    # Candle interval
CANDLE_LIMIT    = 100     # How many recent candles to fetch each tick
                          # Must be > BREAKOUT_PERIOD + 1

# Momentum breakout settings
BREAKOUT_PERIOD = 20

# Execution cost settings
FEE_RATE      = 0.001    # 0.1% per trade
SLIPPAGE_RATE = 0.0005   # 0.05% per trade

# Starting paper portfolio per symbol (only used if no state file exists yet)
STARTING_QUOTE_BALANCE = 1000.0
STARTING_BASE_BALANCE  = 0.0

# File paths
STATE_FILE  = "live_state.json"   # Portfolio balances, persisted between runs
STATUS_FILE = "STATUS.md"         # Human-readable status, shown on GitHub


# =============================================================================
# DATA FETCHING
# =============================================================================

def get_latest_candles(symbol):
    """
    Fetch the most recent CANDLE_LIMIT candles for a symbol.
    Unlike the backtester, we do not use fixed dates — we always
    want the latest available market data.
    """
    url = f"{BASE_URL}/api/v3/klines"
    params = {
        "symbol":   symbol,
        "interval": INTERVAL,
        "limit":    CANDLE_LIMIT
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def format_candle(raw_candle):
    """
    Convert one raw Binance candle into a cleaner dictionary.
    """
    return {
        "open_time": datetime.fromtimestamp(raw_candle[0] / 1000),
        "open":      float(raw_candle[1]),
        "high":      float(raw_candle[2]),
        "low":       float(raw_candle[3]),
        "close":     float(raw_candle[4]),
        "volume":    float(raw_candle[5])
    }


def get_close_prices(candles):
    """
    Extract only the close prices from a list of formatted candles.
    """
    return [candle["close"] for candle in candles]


# =============================================================================
# SIGNAL GENERATION
# =============================================================================

def get_breakout_details(close_prices):
    """
    Calculate the breakout signal and return full details:
    - signal: BUY, SELL, or HOLD
    - current_price: the latest close
    - window_high: highest price in the lookback window
    - window_low: lowest price in the lookback window
    - reason: human-readable explanation of the decision

    Returns all details so we can use them in both the terminal
    output and the STATUS.md file.
    """
    if len(close_prices) < BREAKOUT_PERIOD + 1:
        return {
            "signal":        "HOLD",
            "current_price": close_prices[-1],
            "window_high":   None,
            "window_low":    None,
            "reason":        "Not enough candles yet"
        }

    current_price     = close_prices[-1]
    window            = close_prices[-(BREAKOUT_PERIOD + 1):-1]
    window_high       = max(window)
    window_low        = min(window)

    if current_price > window_high:
        signal = "BUY"
        reason = f"Price {round(current_price, 4)} broke above {BREAKOUT_PERIOD}-candle high of {round(window_high, 4)}"
    elif current_price < window_low:
        signal = "SELL"
        reason = f"Price {round(current_price, 4)} broke below {BREAKOUT_PERIOD}-candle low of {round(window_low, 4)}"
    else:
        signal = "HOLD"
        reason = f"Price {round(current_price, 4)} within range ({round(window_low, 4)} — {round(window_high, 4)})"

    return {
        "signal":        signal,
        "current_price": current_price,
        "window_high":   window_high,
        "window_low":    window_low,
        "reason":        reason
    }


# =============================================================================
# PERSISTENT STATE
# =============================================================================

def load_state():
    """
    Load the portfolio state from the state file.

    If no state file exists yet (first ever run), initialise a fresh
    portfolio for every symbol using the starting balances defined above.

    State structure:
    {
        "BTCUSDT": {"quote_balance": 1000.0, "base_balance": 0.0, "trade_count": 0},
        "ETHUSDT": {"quote_balance": 1000.0, "base_balance": 0.0, "trade_count": 0},
    }
    """
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    # No state file yet — create a fresh portfolio for each symbol
    state = {}
    for entry in SYMBOLS:
        symbol = entry["symbol"]
        state[symbol] = {
            "quote_balance": STARTING_QUOTE_BALANCE,
            "base_balance":  STARTING_BASE_BALANCE,
            "trade_count":   0
        }
    return state


def save_state(state):
    """
    Save the current portfolio state to the state file.
    Called after every tick so the bot remembers positions between runs.
    """
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# =============================================================================
# TRADE SIMULATION
# =============================================================================

def simulate_trade(signal, current_price, quote_balance, base_balance, symbol_entry):
    """
    Simulate a buy or sell based on the signal.
    Applies fee and slippage exactly as the backtester does.

    Returns updated quote_balance, base_balance, and a description of what happened.
    """
    base         = symbol_entry["base"]
    quote        = symbol_entry["quote"]
    action_taken = None

    if signal == "BUY" and quote_balance > 0:
        # Apply slippage — price moves slightly against us when buying
        execution_price  = current_price * (1 + SLIPPAGE_RATE)
        # Apply fee — deduct from quote before converting
        amount_after_fee = quote_balance * (1 - FEE_RATE)
        base_balance     = amount_after_fee / execution_price
        quote_balance    = 0.0
        action_taken     = f"BUY — bought {round(base_balance, 6)} {base} at {round(execution_price, 4)} {quote}"

    elif signal == "SELL" and base_balance > 0:
        # Apply slippage — price moves slightly against us when selling
        execution_price = current_price * (1 - SLIPPAGE_RATE)
        gross_quote     = base_balance * execution_price
        # Apply fee — deduct from proceeds
        quote_balance   = gross_quote * (1 - FEE_RATE)
        base_balance    = 0.0
        action_taken    = f"SELL — sold for {round(quote_balance, 4)} {quote} at {round(execution_price, 4)} {quote}"

    return quote_balance, base_balance, action_taken


# =============================================================================
# STATUS FILE
# =============================================================================

def save_status(timestamp, symbol_statuses):
    """
    Write a human-readable STATUS.md file that gets committed back to GitHub.
    Anyone visiting the repo can see exactly what the bot is doing right now.

    symbol_statuses is a list of dicts, one per symbol, containing all the
    details needed to build a clear status block.
    """
    lines = []
    lines.append("# Live Bot Status")
    lines.append("")
    lines.append(f"**Last updated:** {timestamp} UTC")
    lines.append("")
    lines.append(f"**Candle size:** {INTERVAL} | **Runs every:** ~10 minutes | **Breakout period:** {BREAKOUT_PERIOD} candles | **Fee:** {FEE_RATE*100}% | **Slippage:** {SLIPPAGE_RATE*100}%")
    lines.append("")
    lines.append("---")
    lines.append("")

    for s in symbol_statuses:
        symbol          = s["symbol"]
        base            = s["base"]
        quote           = s["quote"]
        current_price   = s["current_price"]
        signal          = s["signal"]
        reason          = s["reason"]
        quote_balance   = s["quote_balance"]
        base_balance    = s["base_balance"]
        portfolio_value = s["portfolio_value"]
        pnl             = s["pnl"]
        pnl_pct         = s["pnl_pct"]
        trade_count     = s["trade_count"]
        action_taken    = s["action_taken"]

        # Signal emoji for quick visual scan
        if signal == "BUY":
            signal_icon = "🟢 BUY"
        elif signal == "SELL":
            signal_icon = "🔴 SELL"
        else:
            signal_icon = "⚪ HOLD"

        # P/L colour indicator
        pnl_display = f"+{round(pnl, 2)}" if pnl >= 0 else str(round(pnl, 2))
        pnl_pct_display = f"+{round(pnl_pct, 2)}%" if pnl_pct >= 0 else f"{round(pnl_pct, 2)}%"

        lines.append(f"## {symbol}")
        lines.append("")
        lines.append(f"| | |")
        lines.append(f"|---|---|")
        lines.append(f"| **Current price** | {round(current_price, 4)} {quote} |")
        lines.append(f"| **Signal** | {signal_icon} |")
        lines.append(f"| **Reason** | {reason} |")
        if action_taken:
            lines.append(f"| **Last action** | {action_taken} |")
        lines.append(f"| **{quote} balance** | {round(quote_balance, 2)} |")
        lines.append(f"| **{base} balance** | {round(base_balance, 6)} |")
        lines.append(f"| **Portfolio value** | {round(portfolio_value, 2)} {quote} |")
        lines.append(f"| **P/L** | {pnl_display} {quote} ({pnl_pct_display}) |")
        lines.append(f"| **Total trades** | {trade_count} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("*This file is auto-generated every 10 minutes by the live trading bot.*")

    with open(STATUS_FILE, "w") as f:
        f.write("\n".join(lines))


# =============================================================================
# MAIN TICK
# =============================================================================

def run_tick():
    """
    One full tick of the live bot:
    1. Load current portfolio state
    2. For each symbol:
       a. Fetch latest candles
       b. Get breakout signal and details
       c. Simulate a trade if signal is actionable
       d. Print status to terminal
    3. Save updated state
    4. Write STATUS.md for GitHub visibility
    """
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    state = load_state()

    print("=" * 60)
    print(f"LIVE BOT TICK — {now} UTC")
    print("=" * 60)

    symbol_statuses = []

    for entry in SYMBOLS:
        symbol = entry["symbol"]
        base   = entry["base"]
        quote  = entry["quote"]

        # 1. Fetch and format latest candles
        try:
            raw_candles       = get_latest_candles(symbol)
            formatted_candles = [format_candle(c) for c in raw_candles]
            close_prices      = get_close_prices(formatted_candles)
        except Exception as e:
            print(f"{symbol} | ERROR fetching data: {e}")
            continue

        # 2. Get signal and full breakout details
        details       = get_breakout_details(close_prices)
        signal        = details["signal"]
        current_price = details["current_price"]
        reason        = details["reason"]

        # 3. Load current balances for this symbol
        quote_balance = state[symbol]["quote_balance"]
        base_balance  = state[symbol]["base_balance"]

        # 4. Simulate trade if signal is actionable
        quote_balance, base_balance, action_taken = simulate_trade(
            signal, current_price, quote_balance, base_balance, entry
        )

        # 5. Update state
        if action_taken:
            state[symbol]["trade_count"] += 1

        state[symbol]["quote_balance"] = quote_balance
        state[symbol]["base_balance"]  = base_balance

        # 6. Calculate portfolio value and P/L
        portfolio_value = quote_balance + (base_balance * current_price)
        pnl             = portfolio_value - STARTING_QUOTE_BALANCE
        pnl_pct         = (pnl / STARTING_QUOTE_BALANCE) * 100

        # 7. Print terminal status
        print(f"\n{symbol}")
        print(f"  Price:     {round(current_price, 4)} {quote}")
        print(f"  Signal:    {signal}")
        print(f"  Reason:    {reason}")
        if action_taken:
            print(f"  Action:    {action_taken}")
        else:
            print(f"  Action:    No trade")
        print(f"  Portfolio: {round(quote_balance, 2)} {quote} | {round(base_balance, 6)} {base} | Value: {round(portfolio_value, 2)} {quote}")
        pnl_str = f"+{round(pnl, 2)}" if pnl >= 0 else str(round(pnl, 2))
        print(f"  P/L:       {pnl_str} {quote} ({round(pnl_pct, 2)}%)")
        print(f"  Trades:    {state[symbol]['trade_count']} total")

        # 8. Collect status data for STATUS.md
        symbol_statuses.append({
            "symbol":          symbol,
            "base":            base,
            "quote":           quote,
            "current_price":   current_price,
            "signal":          signal,
            "reason":          reason,
            "quote_balance":   quote_balance,
            "base_balance":    base_balance,
            "portfolio_value": portfolio_value,
            "pnl":             pnl,
            "pnl_pct":         pnl_pct,
            "trade_count":     state[symbol]["trade_count"],
            "action_taken":    action_taken
        })

    print()

    # 9. Save state and write STATUS.md
    save_state(state)
    save_status(now, symbol_statuses)
    print(f"State saved to {STATE_FILE}")
    print(f"Status written to {STATUS_FILE}")
    print("=" * 60)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_tick()