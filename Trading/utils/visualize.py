from typing import List
from matplotlib.dates import date2num
import matplotlib.pyplot as plt
from Trading.algo.strategy.trade import Trade

# Visualizations for trades

def plot_trades_gant(all_trades: List[List[Trade]]):
    fig, ax = plt.subplots(figsize=(10, 6))
    legend_labels = []
    for trades in all_trades:
        trades.sort(key=lambda x: x.entry_date)
        trade_labels = []
        trade_start_dates = []
        trade_end_dates = []
        legend_labels.append(trades[0].symbol)
        for trade in trades:
            trade_labels.append(f"Trade {len(trade_labels) + 1}")
            trade_start_dates.append(trade.entry_date)
            trade_end_dates.append(trade.exit_date)

        # Convert dates to numerical format for plotting
        trade_start_dates_num = date2num(trade_start_dates)
        trade_end_dates_num = date2num(trade_end_dates)

        ax.barh(trade_labels, trade_end_dates_num - trade_start_dates_num, left=trade_start_dates_num, height=0.5)

    ax.set_xlabel('Timeline')
    ax.set_ylabel('Trades')
    ax.set_title('Trade Openings Overlapping Timelines')
    ax.legend(legend_labels)
    ax.xaxis_date()

    plt.show()
