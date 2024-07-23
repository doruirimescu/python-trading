import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

def fetch_data(assets, start_date, end_date):
    # Fetch the historical price data for the assets
    return yf.download(assets, start=start_date, end=end_date)['Adj Close']

def calculate_ratios(data):
    ratio_data = {}
    k = 1
    for i in data.columns:
        for j in data.columns:
            if j > i:
                ratio_data[f"{i}/{j}"] = data[i] / data[j]
        k += 1
    return pd.DataFrame(ratio_data)

# Assuming 'ratios' is a DataFrame with your ratio data
def plot_moving_average(ratios, name, window=50):
    ratio_data = ratios[name]
    # Calculate the moving average
    moving_avg = ratio_data.rolling(window=window).mean()

    # Plot
    plt.figure(figsize=(14,7))
    plt.plot(ratio_data, label='Ratio')
    plt.plot(moving_avg, label=f'{window}-Day Moving Average', linestyle='--')
    plt.title(f'Ratio {name} with Moving Average')
    plt.legend()
    plt.grid(True)
    plt.show()

def calculate_rsi(data, period=50):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def plot_moving_average_for_all_ratios(ratios, window=50):
    for column in ratios.columns:
        # Calculate the moving average for the current ratio
        moving_avg = ratios[column].rolling(window=window).mean()

        # Plot
        plt.figure(figsize=(14,7))
        plt.plot(ratios[column], label='Ratio')
        plt.plot(moving_avg, label=f'{window}-Day Moving Average', linestyle='--')
        plt.title(f'{column} with Moving Average')
        plt.legend()
        plt.grid(True)
        plt.show()

def plot_moving_average_with_rsi(ratios, name, window=50, rsi_period=14):
    ratio_data = ratios[name]
    moving_avg = ratio_data.rolling(window=window).mean()
    rsi = calculate_rsi(ratio_data, period=rsi_period)

    # Create subplots with linked x-axes
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 14), sharex=True)

    # Plot Ratio and Moving Average
    ax1.plot(ratio_data, label='Ratio')
    ax1.plot(moving_avg, label=f'{window}-Day Moving Average', linestyle='--')
    ax1.set_title(f'Ratio {name} with Moving Average')
    ax1.legend()
    ax1.grid(True)

    # Plot RSI
    ax2.plot(rsi, label='RSI', color='purple')
    ax2.axhline(70, linestyle='--', color='red', label='Overbought (70)')
    ax2.axhline(40, linestyle='--', color='green', label='Oversold (40)')
    ax2.set_title(f'RSI for {name}')
    ax2.legend()
    ax2.grid(True)

    plt.show()



def plot_moving_average_with_inverse(ratios, window=14):
    for column in ratios.columns:
        # Calculate the moving average for the current ratio
        moving_avg = ratios[column].rolling(window=window).mean()

        # Calculate the inverse of the ratio and its moving average
        inverse_ratio = 1 / ratios[column]
        inverse_moving_avg = inverse_ratio.rolling(window=window).mean()

        # Normalize to remove offset, ensuring both ratios start from the same point
        ratios[column] = ratios[column] / ratios[column].iloc[0]
        inverse_ratio = inverse_ratio / inverse_ratio.iloc[0]

        # Plot
        plt.figure(figsize=(14,7))
        plt.plot(ratios[column], label='Ratio')
        plt.plot(moving_avg / moving_avg.iloc[0], label=f'{window}-Day Moving Average', linestyle='--')
        plt.plot(inverse_ratio, label='Inverse Ratio', alpha=0.6)
        plt.plot(inverse_moving_avg / inverse_moving_avg.iloc[0], label=f'Inverse {window}-Day Moving Average', linestyle='-.', alpha=0.6)
        plt.title(f'{column} with Moving Average and Inverse')
        plt.legend()
        plt.grid(True)
        plt.show()

# assets = ["SLV", "GLD", "PPLT", "PALL", "SPY"]
# assets = ["SLV", "AG", "PAAS", "HL", "CDE", "FSM", "EXK", "SVM", "SILV", "MAG", "WPM"]
# assets = ["SI=F", "^DJI"]

#assets = ["AMD", "INTC"]
assets = ["BTC", "BCH", "LTC", "AMD", "INTC", "SLV", "AG", "PAAS", "HL", "CDE"]

#FSM/CDM, HL/PAAS, MAG/CDE

START_DATE = "2015-08-01"
END_DATE = "2024-03-1"
data = fetch_data(assets, START_DATE, END_DATE)
print(data.head())
ratios = calculate_ratios(data)
print(ratios.head())
plot_moving_average_for_all_ratios(ratios)
# for column in ratios.columns:
#     plot_moving_average_with_rsi(ratios, column, rsi_period=60)

# print(ratios.head())
# ratios["PALL/SLV"].to_csv("pall_slv_ratio.csv")
