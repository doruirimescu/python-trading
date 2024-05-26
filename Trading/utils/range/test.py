import yfinance as yf
from Trading.symbols.google_search_symbol import get_yfinance_symbol_url

# Define the ticker symbol
ticker_symbol = "AEWUL.XC"

# Get the stock information
stock = yf.Ticker(ticker_symbol)

# Fetch the cash flow statement
cashflow = stock.cashflow

# Display the free cash flow
free_cash_flow = cashflow.loc['Free Cash Flow']
print(free_cash_flow)
