import requests
from datetime import datetime, timezone

BASE_URL = "https://data-api.binance.vision"

# --- STAGE 3: Multi-symbol configuration ---
# Add or remove symbols here to include them in the backtest.
# Each entry needs a symbol (Binance pair), base asset, and quote asset.
SYMBOLS = [
    {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT"},
    {"symbol": "ETHUSDT", "base": "ETH", "quote": "USDT"},
    {"symbol": "SOLUSDT", "base": "SOL", "quote": "USDT"},
    {"symbol": "BNBUSDT", "base": "BNB", "quote": "USDT"},
    {"symbol": "XRPUSDT", "base": "XRP", "quote": "USDT"},
    {"symbol": "ADAUSDT", "base": "ADA", "quote": "USDT"},
]

INTERVAL = "1h"

# --- STAGE 2: Fixed backtest window ---
# Define exactly which period of history to test.
# This makes results reproducible — same dates always return the same candles.
# Format: "YYYY-MM-DD"
START_DATE = "2026-01-01"
END_DATE   = "2026-06-22"

# Starting paper portfolio
STARTING_QUOTE_BALANCE = 1000.0
STARTING_BASE_BALANCE  = 0.0

# Momentum breakout settings
# The strategy buys when price breaks above the highest close in the last
# BREAKOUT_PERIOD candles, and sells when it breaks below the lowest.
BREAKOUT_PERIOD = 20

# --- STAGE 1: Execution cost settings ---
# Fee rate: 0.1% is Binance standard. Deducted on every buy and sell.
FEE_RATE = 0.001
# Slippage rate: 0.05% simulates not getting the exact close price.
# Price moves slightly against you — higher when buying, lower when selling.
SLIPPAGE_RATE = 0.0005


def get_klines(symbol):
    """
    Fetch raw candlestick data from Binance for the chosen symbol.
    Uses a fixed start and end date so results are always reproducible.

    Binance returns a maximum of 1000 candles per request. If the date range
    covers more than 1000 candles, we paginate — making multiple requests
    and stitching the results together until we have the full window.
    """
    url = f"{BASE_URL}/api/v3/klines"

    # Convert date strings into millisecond timestamps.
    # datetime.strptime turns "2024-10-01" into a datetime object.
    # .replace(tzinfo=timezone.utc) pins it to UTC so Binance gets the right time.
    # .timestamp() converts to seconds since 1970, * 1000 gives milliseconds.
    start_ms = int(datetime.strptime(START_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms   = int(datetime.strptime(END_DATE,   "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    all_candles   = []         # we collect every candle here across all requests
    current_start = start_ms   # this moves forward with each request

    while True:
        params = {
            "symbol":    symbol,
            "interval":  INTERVAL,
            "startTime": current_start,
            "endTime":   end_ms,
            "limit":     1000  # maximum Binance allows per request
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        batch = response.json()

        # If Binance returned nothing, we are done
        if not batch:
            break

        all_candles.extend(batch)

        # If we received fewer than 1000 candles, this was the last page
        if len(batch) < 1000:
            break

        # Otherwise, move the start forward to just after the last candle received.
        # We add 1 millisecond so we don't fetch the last candle again.
        last_candle_open_time = batch[-1][0]
        current_start = last_candle_open_time + 1

    print(f"Fetched {len(all_candles)} candles across {symbol} from {START_DATE} to {END_DATE}")

    return all_candles


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
    Returns a plain Python list of floats.
    """
    close_prices = []
    for candle in candles:
        close_prices.append(candle["close"])
    return close_prices


def generate_breakout_signal(close_prices):
    """
    Generate a BUY, SELL, or HOLD signal based on momentum breakout.

    Looks at the highest and lowest close prices over the last BREAKOUT_PERIOD
    candles, excluding the current candle. If the current price breaks above
    that range it signals bullish momentum. If it breaks below, bearish.

    BUY  when current price > highest close in the lookback window
    SELL when current price < lowest close in the lookback window
    HOLD otherwise

    We exclude the current candle from the window so we are not comparing
    the price to itself, which would trigger a signal on almost every candle.
    """
    # Need at least BREAKOUT_PERIOD + 1 candles:
    # BREAKOUT_PERIOD for the window, plus 1 for the current price
    if len(close_prices) < BREAKOUT_PERIOD + 1:
        return "HOLD"

    # Current price is the most recent close
    current_price = close_prices[-1]

    # The lookback window is the BREAKOUT_PERIOD candles before the current one
    window = close_prices[-(BREAKOUT_PERIOD + 1):-1]

    highest_in_window = max(window)
    lowest_in_window  = min(window)

    # Bullish breakout: price breaks above the recent high
    if current_price > highest_in_window:
        return "BUY"

    # Bearish breakout: price breaks below the recent low
    elif current_price < lowest_in_window:
        return "SELL"

    else:
        return "HOLD"


def backtest_strategy(candles, starting_quote_balance, starting_base_balance):
    """
    Walk through the candles one by one and simulate what the bot
    would have done through time, using the momentum breakout strategy.

    For each candle:
    1. Extract all close prices seen so far (no future data)
    2. Generate a breakout signal
    3. Simulate a buy or sell if the signal and balance allow it
    4. Log every trade with execution price and fee details
    """
    quote_balance = starting_quote_balance
    base_balance  = starting_base_balance
    trade_log     = []

    for i in range(len(candles)):
        # Only use candles up to the current moment — no lookahead
        current_candles = candles[:i + 1]
        close_prices    = get_close_prices(current_candles)

        # Ask the strategy for a signal
        signal = generate_breakout_signal(close_prices)

        current_price = close_prices[-1]
        current_time  = current_candles[-1]["open_time"]

        if signal == "BUY" and quote_balance > 0:
            # --- STAGE 1: Apply slippage ---
            # When buying, price moves slightly against us (higher than close)
            execution_price = current_price * (1 + SLIPPAGE_RATE)

            # --- STAGE 1: Apply fee ---
            # Deduct the fee from our quote balance before converting
            amount_after_fee = quote_balance * (1 - FEE_RATE)

            # Convert remaining quote into base asset at the execution price
            base_balance  = amount_after_fee / execution_price
            quote_balance = 0.0

            trade_log.append({
                "time":            current_time,
                "action":          "BUY",
                "signal_price":    current_price,
                "execution_price": execution_price,
                "fee_paid":        amount_after_fee * FEE_RATE,
                "quote_balance":   quote_balance,
                "base_balance":    base_balance
            })

        elif signal == "SELL" and base_balance > 0:
            # --- STAGE 1: Apply slippage ---
            # When selling, price moves slightly against us (lower than close)
            execution_price = current_price * (1 - SLIPPAGE_RATE)

            # Convert all base asset into quote currency at the execution price
            gross_quote   = base_balance * execution_price

            # --- STAGE 1: Apply fee ---
            quote_balance = gross_quote * (1 - FEE_RATE)
            base_balance  = 0.0

            trade_log.append({
                "time":            current_time,
                "action":          "SELL",
                "signal_price":    current_price,
                "execution_price": execution_price,
                "fee_paid":        gross_quote * FEE_RATE,
                "quote_balance":   quote_balance,
                "base_balance":    base_balance
            })

    # Value any remaining base asset at the final close price
    final_price         = candles[-1]["close"]
    final_account_value = quote_balance + (base_balance * final_price)
    profit_loss         = final_account_value - starting_quote_balance

    return quote_balance, base_balance, final_account_value, profit_loss, trade_log


def main():
    # Print shared backtest settings once at the top
    print("=" * 60)
    print("BACKTEST SETTINGS")
    print("=" * 60)
    print("Strategy:      ", "Momentum Breakout")
    print("Interval:      ", INTERVAL)
    print("Breakout period:", BREAKOUT_PERIOD)
    print("Start date:    ", START_DATE)
    print("End date:      ", END_DATE)
    print("Fee rate:      ", FEE_RATE)
    print("Slippage rate: ", SLIPPAGE_RATE)
    print("Starting USDT: ", STARTING_QUOTE_BALANCE)
    print()

    # --- STAGE 3: Loop through every symbol and run the full backtest ---
    for entry in SYMBOLS:
        symbol = entry["symbol"]
        base   = entry["base"]
        quote  = entry["quote"]

        # 1. Fetch raw candle data for this symbol
        raw_data = get_klines(symbol)

        # 2. Format raw candles into clean dictionaries
        formatted_data = []
        for candle in raw_data:
            formatted_data.append(format_candle(candle))

        # 3. Run the backtest for this symbol
        quote_balance, base_balance, final_account_value, profit_loss, trade_log = backtest_strategy(
            formatted_data,
            STARTING_QUOTE_BALANCE,
            STARTING_BASE_BALANCE
        )

        # 4. Print a clean summary for this symbol
        print("=" * 60)
        print(f"RESULTS: {symbol}")
        print("=" * 60)
        print("Candles used:         ", len(formatted_data))
        print(f"Final {quote} balance: ", round(quote_balance, 2))
        print(f"Final {base} balance:  ", round(base_balance, 6))
        print(f"Final account value:   ", round(final_account_value, 2), quote)
        print(f"Profit / Loss:         ", round(profit_loss, 2), quote)
        print("Number of trades:     ", len(trade_log))
        print()


if __name__ == "__main__":
    main()