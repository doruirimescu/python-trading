#implemented from https://youtu.be/XBcMiYK7qYY
import talib
import matplotlib.pyplot as plt
import mplfinance as mpf
from typing import List
from datetime import datetime
from Trading.algo.strategy.trade import Trade
from Trading.utils.timeseries import slice_data_np


def calculate_indicators(data):
    # Calculate 200-day SMA
    sma200 = talib.SMA(data['close'], timeperiod=200)

    # Calculate RSI
    rsi = talib.RSI(data['close'], timeperiod=5)

    return sma200, rsi

def should_enter_trade(data):
    sma200, rsi = calculate_indicators(data)

    # Get the last values
    last_close_price = data['close'][-1]
    last_sma200 = sma200[-1]
    last_rsi = rsi[-1]

    is_rsi_below_30 = last_rsi < 30
    is_rsi_down_3_days_in_a_row = rsi[-3] > rsi[-2] > rsi[-1]
    was_rsi_below_60_3_days_ago = rsi[-3] < 60

    is_above_sma200 = last_close_price > last_sma200


    # Trade entry condition
    if is_rsi_below_30 and is_rsi_down_3_days_in_a_row and was_rsi_below_60_3_days_ago and is_above_sma200:
        return True
    return False

def should_exit_trade(data):
    _, rsi = calculate_indicators(data)
    return rsi[-1] > 49


def get_trades(data, entry_dates: List[datetime]):
    _, rsi = calculate_indicators(data)
    exit_dates = []
    trades = []
    n_days = len(data['date'])
    for i, d in enumerate(data['date']):
        if d in entry_dates:
            open_price = data['open'][i]
            for j in range(i + 1, n_days):
                if should_exit_trade(slice_data_np(data, j + 1)):
                    exit_dates.append(data['date'][j])
                    close_price = data['close'][j]

                    t = Trade(entry_date=d, exit_date=data['date'][j], open_price=open_price, close_price=close_price, cmd=0)
                    trades.append(t)
                    break
    return trades

def plot_data(data):
    ema200, rsi = calculate_indicators(data)

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


    # Create the plot
    fig, axes = mpf.plot(df,
                        type='candle',
                        style='charles',
                        addplot=[addplot_ema200, addplot_rsi],
                        figratio=(2, 1),
                        volume=False,
                        title='Candlestick chart with SMA200 and RSI',
                        returnfig=True)
    plt.show()
