import yfinance as yf


def fetch_pvgo_fundamentals(ticker_symbol):
    """Fetch the ticker-specific inputs, which can be cached as one unit."""
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        forward_eps = info.get('forwardEps')
        beta = info.get('beta')

        if None in (current_price, forward_eps, beta):
            raise ValueError("Incomplete stock data retrieved from yfinance.")

        return {
            "current_price": float(current_price),
            "forward_eps": float(forward_eps),
            "beta": float(beta),
        }
    except Exception as e:
        return f"Error fetching PVGO fundamentals for {ticker_symbol.upper()}: {e}"


def fetch_risk_free_rate():
    """Fetch the 10-year Treasury yield using yfinance's lighter price API."""
    try:
        tnx = yf.Ticker("^TNX")
        fast = tnx.fast_info
        tnx_price = None
        for key in ("lastPrice", "previousClose"):
            try:
                tnx_price = fast[key]
            except (KeyError, TypeError):
                continue
            if tnx_price is not None:
                break
        if tnx_price is None:
            tnx_price = (
                getattr(fast, "last_price", None)
                or getattr(fast, "previous_close", None)
            )

        if tnx_price is None:
            raise ValueError("No ^TNX price returned by yfinance.")

        return float(tnx_price) / 100
    except Exception as e:
        return f"Error fetching the risk-free rate: {e}"


def compute_pvgo(fundamentals, risk_free_rate, ticker_symbol, market_risk_premium=0.05):
    """Calculate PVGO without making network requests."""
    current_price = fundamentals["current_price"]
    forward_eps = fundamentals["forward_eps"]
    beta = fundamentals["beta"]

    cost_of_equity = risk_free_rate + (beta * market_risk_premium)
    if current_price <= 0:
        return "Error calculating PVGO: Current price must be positive."
    if cost_of_equity <= 0:
        return "Error calculating PVGO: Cost of equity must be positive."

    no_growth_value = forward_eps / cost_of_equity
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


def calculate_pvgo(ticker_symbol, market_risk_premium=0.05):
    """Backward-compatible one-shot PVGO calculation."""
    fundamentals = fetch_pvgo_fundamentals(ticker_symbol)
    if isinstance(fundamentals, str):
        return fundamentals

    risk_free_rate = fetch_risk_free_rate()
    if isinstance(risk_free_rate, str):
        return risk_free_rate

    return compute_pvgo(
        fundamentals,
        risk_free_rate,
        ticker_symbol,
        market_risk_premium,
    )
