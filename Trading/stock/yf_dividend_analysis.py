import yfinance as yf
from datetime import datetime, timedelta

def get_dividend_data(ticker_symbol):
    # Get the data for the last 10 years
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365 * 10)

    # Fetch the stock data
    stock = yf.Ticker(ticker_symbol)
    dividend_history = stock.dividends[start_date:]
    current_div_yield = stock.info.get("dividendYield", 0) * 100  # Convert to percentage

    return dividend_history, current_div_yield

def calculate_dividend_growth(dividend_history):
    if len(dividend_history) < 2:
        return None

    years = sorted(dividend_history.index.year.unique())
    initial_year = years[0]
    final_year = years[-1]
    initial_dividend = dividend_history[dividend_history.index.year == initial_year].sum()
    final_dividend = dividend_history[dividend_history.index.year == final_year].sum()

    if initial_dividend == 0 or final_dividend == 0:
        return None

    years_diff = final_year - initial_year
    dividend_growth_rate = ((final_dividend / initial_dividend) ** (1 / years_diff) - 1) * 100

    return dividend_growth_rate

def main():
    ticker_symbol = input("Enter the ticker symbol of the financial instrument: ").strip()
    dividend_history, current_div_yield = get_dividend_data(ticker_symbol)

    if not dividend_history.empty:
        print(f"Dividend history for the last 10 years:\n{dividend_history}")
        print(f"Current dividend yield: {current_div_yield:.2f}%")

        dividend_growth_rate = calculate_dividend_growth(dividend_history)
        if dividend_growth_rate is not None:
            print(f"The dividend has grown by approximately {dividend_growth_rate:.2f}% per year over the last 10 years.")
        else:
            print("Unable to calculate the dividend growth rate.")
    else:
        print("No dividend data available for the given financial instrument.")

if __name__ == "__main__":
    main()
