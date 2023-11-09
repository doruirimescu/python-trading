#implemented from https://youtu.be/XBcMiYK7qYY
import talib
import numpy as np

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Trade:
    cmd: int #0 buy, 1 sell
    entry_date: datetime
    exit_date: datetime
    open_price: float
    close_price: float


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

def get_trades(data, enter_dates, spread = 0.0):
    total_profit = 0
    loss = 0
    profit = 0
    n_loss = 0
    n_profit = 0
    sma200, rsi = calculate_indicators(data)
    exit_dates = []
    trades = []

    for i, d in enumerate(data['date']):
        if d in enter_dates:
            open_price = data['open'][i]
            for j in range(i + 1, len(data['date'])):
                should_close_prematurely = False

                if rsi[j] > 49 or should_close_prematurely:
                    exit_dates.append(data['date'][j])
                    close_price = data['close'][j]

                    t = Trade(entry_date=d, exit_date=data['date'][j], open_price=open_price, close_price=close_price, cmd=0)
                    trades.append(t)
                    trade_profit = close_price - open_price - spread

                    if trade_profit < 0:
                        n_loss += 1
                        loss += trade_profit
                    else:
                        n_profit += 1
                        profit += trade_profit
                    total_profit += (trade_profit)
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