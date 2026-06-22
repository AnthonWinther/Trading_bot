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

# State file — portfolio balances are saved here after every tick
# so the bot remembers its positions between runs
STATE_FILE = "live_state.json"


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

def generate_breakout_signal(close_prices):
    """
    Generate a BUY, SELL, or HOLD signal based on momentum breakout.

    BUY  when current price > highest close in the last BREAKOUT_PERIOD candles
    SELL when current price < lowest close in the last BREAKOUT_PERIOD candles
    HOLD otherwise

    The current candle is excluded from the window so we are not
    comparing the price to itself.
    """
    if len(close_prices) < BREAKOUT_PERIOD + 1:
        return "HOLD"

    current_price     = close_prices[-1]
    window            = close_prices[-(BREAKOUT_PERIOD + 1):-1]
    highest_in_window = max(window)
    lowest_in_window  = min(window)

    if current_price > highest_in_window:
        return "BUY"
    elif current_price < lowest_in_window:
        return "SELL"
    else:
        return "HOLD"


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
    base  = symbol_entry["base"]
    quote = symbol_entry["quote"]
    action_taken = None

    if signal == "BUY" and quote_balance > 0:
        # Apply slippage — price moves slightly against us when buying
        execution_price  = current_price * (1 + SLIPPAGE_RATE)
        # Apply fee — deduct from quote before converting
        amount_after_fee = quote_balance * (1 - FEE_RATE)
        base_balance     = amount_after_fee / execution_price
        quote_balance    = 0.0
        action_taken     = f"BUY  | Bought {round(base_balance, 6)} {base} at {round(execution_price, 4)} {quote}"

    elif signal == "SELL" and base_balance > 0:
        # Apply slippage — price moves slightly against us when selling
        execution_price = current_price * (1 - SLIPPAGE_RATE)
        gross_quote     = base_balance * execution_price
        # Apply fee — deduct from proceeds
        quote_balance   = gross_quote * (1 - FEE_RATE)
        base_balance    = 0.0
        action_taken    = f"SELL | Sold for {round(quote_balance, 4)} {quote} at {round(execution_price, 4)} {quote}"

    return quote_balance, base_balance, action_taken


# =============================================================================
# MAIN TICK
# =============================================================================

def run_tick():
    """
    One full tick of the live bot:
    1. Load current portfolio state
    2. For each symbol:
       a. Fetch latest candles
       b. Generate a signal
       c. Simulate a trade if signal is actionable
       d. Print status
    3. Save updated state
    """
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = load_state()

    print("=" * 60)
    print(f"LIVE BOT TICK — {now}")
    print("=" * 60)

    for entry in SYMBOLS:
        symbol = entry["symbol"]
        base   = entry["base"]
        quote  = entry["quote"]

        # 1. Fetch and format latest candles
        try:
            raw_candles       = get_latest_candles(symbol)
            formatted_candles = [format_candle(c) for c in raw_candles]
            close_prices      = get_close_prices(formatted_candles)
            current_price     = close_prices[-1]
        except Exception as e:
            print(f"{symbol} | ERROR fetching data: {e}")
            continue

        # 2. Generate signal
        signal = generate_breakout_signal(close_prices)

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

        # 6. Calculate current portfolio value
        portfolio_value = quote_balance + (base_balance * current_price)

        # 7. Print status for this symbol
        print(f"\n{symbol}")
        print(f"  Price:     {round(current_price, 4)} {quote}")
        print(f"  Signal:    {signal}")
        if action_taken:
            print(f"  Action:    {action_taken}")
        else:
            print(f"  Action:    HOLD — no trade")
        print(f"  Portfolio: {round(quote_balance, 2)} {quote} | {round(base_balance, 6)} {base} | Value: {round(portfolio_value, 2)} {quote}")
        print(f"  Trades:    {state[symbol]['trade_count']} total")

    print()

    # 8. Save updated state so next run picks up where this one left off
    save_state(state)
    print(f"State saved to {STATE_FILE}")
    print("=" * 60)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_tick()