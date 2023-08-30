import yfinance as yf

def get_dividend_yield(ticker_symbol):
    # Fetch the stock data
    stock = yf.Ticker(ticker_symbol)

    # Get dividend yield
    dividend_yield = stock.info.get('dividendYield')

    return dividend_yield

ticker = input("Enter the ticker symbol: ")
dy = get_dividend_yield(ticker)
print(f"The dividend yield for {ticker} is: {dy}")
