#implemented from https://youtu.be/XBcMiYK7qYY
import talib
import numpy as np

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd


# Assuming `data` is a dict with 'open', 'high', 'low', 'close', 'date' as keys and lists of prices/dates as values
def is_bullish_engulfing(open_prices, close_prices):
    # Check if there are at least two candles
    if len(open_prices) < 2 or len(close_prices) < 2:
        return False

    # Get the last two open and close prices
    last_open = open_prices[-1]
    last_close = close_prices[-1]
    prev_open = open_prices[-2]
    prev_close = close_prices[-2]

    # Check for a bullish engulfing pattern
    is_prev_candle_bearish = prev_close <= prev_open
    is_last_candle_bullish = last_close >= last_open
    is_last_candle_engulfing = last_open < prev_close and last_close > prev_open

    # If all conditions are met, it's a bullish engulfing pattern
    return is_last_candle_bullish and is_prev_candle_bearish and is_last_candle_engulfing

def is_bullish_engulfing_all(open_prices, close_prices):
    bullish_engulfing = [False]  # There can't be a pattern on the first day
    for i in range(1, len(open_prices)):
        prev_open = open_prices[i-1]
        prev_close = close_prices[i-1]
        curr_open = open_prices[i]
        curr_close = close_prices[i]

        # Bullish engulfing conditions
        p = 0.001/100
        if curr_open < prev_close*(1-p) and curr_close > prev_open*(1+p) and curr_close > curr_open:
            bullish_engulfing.append(True)
        else:
            bullish_engulfing.append(False)
    return bullish_engulfing


def calculate_indicators(data):
    # Calculate 200-day EMA
    ema200 = talib.EMA(data['close'], timeperiod=200)

    # Calculate RSI
    rsi = talib.RSI(data['close'], timeperiod=14)

    return ema200, rsi

def should_enter_trade(data):
    ema200, rsi = calculate_indicators(data)

    # Get the last values
    last_close_price = data['close'][-1]
    last_ema200 = ema200[-1]
    last_rsi = rsi[-1]
    bullish_engulfing = is_bullish_engulfing_all(data['open'][-3:], data['close'][-3:])[-1]

    # Trade entry condition
    if last_close_price > last_ema200 and last_rsi > 50 and bullish_engulfing:
        return True
    return False

def win_ratio(data, enter_dates, spread = 0.0):
    n_profit_trades = 0
    n_loss_trades = 0

    total_profit = 0
    total_loss = 0
    for i, d in enumerate(data['date']):
        if d in set(enter_dates):
            entry_candle_size = abs(data['close'][i] - data['open'][i])
            stop_loss = 2*entry_candle_size

            stop_loss_price = min(data['open'][i], data['close'][i]) - stop_loss

            take_profit = 4*entry_candle_size
            take_profit_price = max(data['open'][i], data['close'][i]) + take_profit

            for j in range(i, len(data['date'])):
                if data['low'][j] <= stop_loss_price:
                    n_loss_trades+=1
                    total_loss += (stop_loss + spread)
                    break
                elif data['high'][j] >= take_profit_price:
                    n_profit_trades+=1
                    total_profit += take_profit
                    total_loss += spread
                    break

    print(f"Profit trades: {n_profit_trades}, Loss trades: {n_loss_trades}")
    print(f"Win ratio: {n_profit_trades/len(enter_dates)} out of {len(enter_dates)}")
    print(f"Total profit: {total_profit}, Total loss: {total_loss}, Net profit: {total_profit - total_loss}")

    # assert n_profit_trades + n_loss_trades == len(enter_dates), "Number of trades should be equal to number of enter dates"

def plot_data(data):
    ema200, rsi = calculate_indicators(data)

    mpf_style = mpf.make_mpf_style(base_mpf_style='nightclouds', rc={'font.size':8})
    addplot_ema200 = mpf.make_addplot(ema200, color='blue', width=0.7)
    addplot_rsi = mpf.make_addplot(rsi, panel='lower', color='purple', ylabel='RSI')


    import pandas as pd
    # Create a DataFrame
    df = pd.DataFrame(data)

    # Convert the 'date' column to datetime and set as the index
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    # Ensure the column names follow the naming convention required by mplfinance
    df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
    }, inplace=True)

    # add BullishEngulfing row
    df['BullishEngulfing'] = is_bullish_engulfing_all(df['Open'].values, df['Close'].values)



    # Create additional plot for engulfing markers
    df['EngulfingMarker'] = df.apply(lambda row: row['High'] if row['BullishEngulfing'] else None, axis=1)
    engulfing_plot = mpf.make_addplot(df['EngulfingMarker'], type='scatter', markersize=50, marker='^', color='green')


    # Create the plot
    fig, axes = mpf.plot(df,
                        type='candle',
                        style='charles',
                        addplot=[addplot_ema200, addplot_rsi, engulfing_plot],
                        figratio=(2, 1),
                        volume=False,
                        title='Candlestick chart with SMA200 and RSI',
                        returnfig=True)
    plt.show()
