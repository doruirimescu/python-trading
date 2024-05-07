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

# plot a list of values with dates
def plot_list_dates(values: List[float], dates: List, title: str, ylabel: str, peaks, show_cursor=True):
    from datetime import datetime
    import mplcursors
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(10, 6))
    dates = [datetime.fromisoformat(d) for d in dates]
    ax.plot(dates, values)
    ax.set_xlabel('Date')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.xaxis_date()

    if show_cursor:
        cursor = mplcursors.cursor(ax, hover=True)
        # Customize the annotation
        @cursor.connect("add")
        def on_add(sel):
            x_date = mdates.num2date(sel.target[0])  # Convert to datetime
            sel.annotation.set(text=f"{x_date.strftime('%Y-%m-%d')}\nValue: {sel.target[1]:.2f}")
    average_value = sum(values) / len(values)
    # plot average as dotted line
    ax.axhline(average_value, color='orange', linestyle='--', label='Average')

    # plot standard deviation above and below average
    from Trading.utils.calculations import calculate_standard_deviation
    std_dev = calculate_standard_deviation(values)
    STD_SCALER = 1.5
    ax.axhline(average_value + STD_SCALER * std_dev, color='green', linestyle='--', label=f'Above {STD_SCALER} Std Dev')
    ax.axhline(average_value - STD_SCALER * std_dev, color='red', linestyle='--', label=f'Below {STD_SCALER} Std Dev')

    peak_values = peaks["values"]
    peak_dates = peaks["dates"]
    ax.plot(peak_dates, peak_values, 'ro', label='Peaks')

    peaks_above_std = []
    peaks_above_std_dates = []
    for i in range(len(peak_values)):
        if abs(peak_values[i] - average_value) > STD_SCALER*std_dev:
            peaks_above_std.append(peak_values[i])
            peaks_above_std_dates.append(peak_dates[i])
    ax.plot(peaks_above_std_dates, peaks_above_std, 'go', label=f'Peaks outside {STD_SCALER} Std Dev')

    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()
    plt.show()
