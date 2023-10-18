import yfinance as yf
import matplotlib.pyplot as plt
import numpy as np

def plot_dividend_growth(dividends):
    plt.figure(figsize=(10, 6))
    plt.plot(dividends.index, dividends.values, marker='o', linestyle='-')
    plt.title("Dividend Growth Over Time")
    plt.xlabel("Year")
    plt.ylabel("Dividend ($)")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def get_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.info, stock.dividends

def analyze_dividend_sustainability(data):
    try:
        # Basic thresholds
        max_payout_ratio = 80  # Maximum payout ratio
        min_yield = 2.0  # Minimum dividend yield
        max_debt_equity = 0.5  # Maximum debt-to-equity ratio
        min_roe = 10.0  # Minimum Return on Equity
        min_free_cashflow = 1e7  # Minimum free cash flow

        # Data extraction
        payout_ratio = data['payoutRatio'] * 100
        dividend_yield = data['dividendYield'] * 100
        debt_equity = data['debtToEquity'] / 100.0
        roe = data['returnOnEquity'] * 100
        free_cashflow = data['freeCashflow']

        print(f"Payout ratio: {payout_ratio:.2f}%")
        print(f"Dividend yield: {dividend_yield:.2f}%")
        print(f"Debt-to-equity ratio: {debt_equity:.2f}")
        print(f"Return on equity: {roe:.2f}%")
        print(f"Free cash flow: {free_cashflow:.2f}")


        # Check conditions
        if (
            (payout_ratio < max_payout_ratio) and
            (dividend_yield >= min_yield) and
            (debt_equity <= max_debt_equity) and
            (roe >= min_roe) and
            (free_cashflow >= min_free_cashflow)
        ):
            return True, "The stock is worth considering for dividend sustainability."
        else:
            return False, "The stock does not meet the dividend sustainability criteria."
    except KeyError:
        return False, "Not all necessary data is available to evaluate the stock."

# Example usage
ticker = "KEY"  # use the ticker symbol of the stock you want to analyze
data, dividends = get_data(ticker)

is_sustainable, message = analyze_dividend_sustainability(data)
print(f"{ticker}: {message}")

# Filter dividends for the last 10 years
last_10_years_dividends = dividends.last('10Y')

# Plotting the dividend history of the last 10 years
plot_dividend_growth(last_10_years_dividends)
# MED, RAND, IIPR, MO, DOC, UMC, KEY are good examples
