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

def plot_moving_average_with_inverse(ratios, window=50):
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
assets = ["SI=F", "^DJI"]
#FSM/CDM, HL/PAAS, MAG/CDE
data = fetch_data(assets, "1993-01-01", "2023-11-01")
ratios = calculate_ratios(data)
print(ratios.head())
plot_moving_average_for_all_ratios(ratios)

# print(ratios.head())
# ratios["PALL/SLV"].to_csv("pall_slv_ratio.csv")
