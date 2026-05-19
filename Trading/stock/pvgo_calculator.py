import yfinance as yf

def calculate_pvgo(ticker_symbol, market_risk_premium=0.05):
    stock = yf.Ticker(ticker_symbol)

    try:
        # 1. Fetch required metrics from the stock
        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        forward_eps = info.get('forwardEps')
        beta = info.get('beta')

        # 2. Fetch the current risk-free rate (10-Year Treasury Yield)
        tnx = yf.Ticker("^TNX")
        tnx_info = tnx.info
        risk_free_rate = (tnx_info.get('regularMarketPrice') or tnx_info.get('previousClose')) / 100

        # Check if any data is missing
        if None in [current_price, forward_eps, beta, risk_free_rate]:
            raise ValueError("Incomplete data retrieved from yfinance.")

        # 3. Calculate Cost of Equity (CAPM)
        cost_of_equity = risk_free_rate + (beta * market_risk_premium)

        # 4. Calculate No-Growth Value
        no_growth_value = forward_eps / cost_of_equity

        # 5. Calculate PVGO
        pvgo = current_price - no_growth_value

        return {
            "Ticker": ticker_symbol.upper(),
            "Current Price": f"${current_price:.2f}",
            "Forward EPS": f"${forward_eps:.2f}",
            "Beta": beta,
            "Risk-Free Rate": f"{risk_free_rate * 100:.2f}%",
            "Cost of Equity": f"{cost_of_equity * 100:.2f}%",
            "No-Growth Value": f"${no_growth_value:.2f}",
            "PVGO": f"${pvgo:.2f}",
            "PVGO Percentage": f"{(pvgo / current_price) * 100:.2f}%"
        }

    except Exception as e:
        return f"Error calculating PVGO: {e}"
