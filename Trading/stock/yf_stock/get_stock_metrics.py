import yfinance as yf

def get_altman_z_score(ticker):
    # Fetch the company's financial data
    stock = yf.Ticker(ticker)
    financials = stock.financials
    balance_sheet = stock.balance_sheet

    # Extract necessary financial data
    total_assets = balance_sheet.loc['Total Assets']
    total_liabilities = balance_sheet.loc['Total Liabilities Net Minority Interest']
    working_capital = balance_sheet.loc['Current Assets'] - balance_sheet.loc['Current Liabilities']
    retained_earnings = balance_sheet.loc['Retained Earnings']
    ebit = financials.loc['Ebit']
    market_value_of_equity = stock.info['marketCap']
    total_revenue = financials.loc['Total Revenue']

    # Calculate Altman Z-Score components
    a = working_capital.iloc[0] / total_assets.iloc[0]
    b = retained_earnings.iloc[0] / total_assets.iloc[0]
    c = ebit.iloc[0] / total_assets.iloc[0]
    d = market_value_of_equity / total_liabilities.iloc[0]
    e = total_revenue.iloc[0] / total_assets.iloc[0]

    # Altman Z-Score calculation
    z_score = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e

    return z_score

if __name__ == "__main__":
    ticker = input("Enter stock ticker: ")
    z_score = get_altman_z_score(ticker)
    print(f"The Altman Z-Score for {ticker} is: {z_score}")
