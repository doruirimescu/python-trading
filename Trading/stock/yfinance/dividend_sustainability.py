import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd

def plot_dividend_growth(symbol, dividends):
    plt.figure(figsize=(10, 6))
    plt.plot(dividends.index, dividends.values, marker="o", linestyle="-")
    plt.title(f"Dividend History Over Time for {symbol.upper()}")
    plt.xlabel("Year")
    plt.ylabel("Dividend ($)")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def get_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.info, stock.dividends

def analyze_dividend_sustainability(data, dividends, should_print: bool = False, threshold: int = 65):
    """
    Evaluates dividend sustainability and assigns a relative score from 0 to 100.
    """
    score = 0
    metrics_str = {}

    # 1. Payout Ratio (Max 20 pts)
    payout = data.get("payoutRatio")
    if payout is not None:
        payout_pct = payout * 100
        metrics_str['Payout Ratio'] = f"{payout_pct:.2f}%"
        if payout_pct < 40: score += 20
        elif payout_pct < 60: score += 15
        elif payout_pct < 80: score += 10
    else:
        metrics_str['Payout Ratio'] = "N/A"

    # 2. Dividend Yield (Max 15 pts) - Punishes yield traps (>7%)
    yield_val = data.get("dividendYield") / 100
    if yield_val is not None:
        yield_pct = yield_val
        metrics_str['Dividend Yield'] = f"{yield_pct:.2f}%"
        if 3 <= yield_pct <= 5: score += 15
        elif 2 <= yield_pct < 3 or 5 < yield_pct <= 7: score += 10
        elif 1 <= yield_pct < 2: score += 5
        elif yield_pct > 7: score += 5
    else:
        metrics_str['Dividend Yield'] = "N/A"

    # 3. Debt to Equity (Max 15 pts)
    dte = data.get("debtToEquity")
    if dte is not None:
        dte_ratio = dte / 100.0
        metrics_str['Debt to Equity'] = f"{dte_ratio:.2f}"
        if dte_ratio < 0.5: score += 15
        elif dte_ratio < 1.0: score += 10
        elif dte_ratio < 2.0: score += 5
    else:
        metrics_str['Debt to Equity'] = "N/A"

    # 4. Return on Equity (Max 15 pts)
    roe = data.get("returnOnEquity")
    if roe is not None:
        roe_pct = roe * 100
        metrics_str['ROE'] = f"{roe_pct:.2f}%"
        if roe_pct > 15: score += 15
        elif roe_pct > 10: score += 10
        elif roe_pct > 5: score += 5
    else:
        metrics_str['ROE'] = "N/A"

    # 5. Current Ratio (Max 10 pts) - Liquidity check
    cr = data.get("currentRatio")
    if cr is not None:
        metrics_str['Current Ratio'] = f"{cr:.2f}"
        if cr > 1.5: score += 10
        elif cr > 1.0: score += 5
    else:
        metrics_str['Current Ratio'] = "N/A"

    # 6. Free Cash Flow (Max 10 pts)
    fcf = data.get("freeCashflow")
    if fcf is not None:
        metrics_str['Free Cash Flow'] = f"${fcf:,.0f}"
        if fcf > 0: score += 10
    else:
        metrics_str['Free Cash Flow'] = "N/A"

    # 7. 5-Year Dividend Growth (Max 15 pts)
    growth_score = 0
    metrics_str['5Y Div Growth'] = "N/A"
    if not dividends.empty:
        try:
            # Resample by year end to calculate CAGR
            annual_divs = dividends.resample('YE').sum()
            if len(annual_divs) >= 5:
                past_val = annual_divs.iloc[-5]
                current_val = annual_divs.iloc[-1]
                if past_val > 0:
                    cagr_pct = ((current_val / past_val) ** (1/4) - 1) * 100
                    metrics_str['5Y Div Growth'] = f"{cagr_pct:.2f}%"
                    if cagr_pct > 10: growth_score = 15
                    elif cagr_pct > 5: growth_score = 10
                    elif cagr_pct > 0: growth_score = 5
        except Exception:
            pass

    score += growth_score

    # Define a threshold for "Sustainable"
    is_sustainable = score >= threshold

    if should_print:
        print(f"\n--- Metrics ---")
        for k, v in metrics_str.items():
            print(f"{k}: {v}")
        print(f"Total Score: {score}/100")
        print("--------------------")

    return is_sustainable, score, yield_val, metrics_str

def analyze_and_plot(ticker: str):
    print(f"\nEvaluating {ticker.upper()}...")
    data, dividends = get_data(ticker)

    is_sustainable, score, yield_val, metrics = analyze_dividend_sustainability(data, dividends, should_print=True)

    status_msg = "Sustainable" if is_sustainable else "Risky / Needs review"
    print(f"Status for {ticker.upper()}: {status_msg}")

    # Plot last 10 years
    if not dividends.empty:
        cutoff = dividends.index[-1] - pd.DateOffset(years=10)
        last_10_years = dividends[dividends.index >= cutoff]
        plot_dividend_growth(ticker, last_10_years)
    else:
        print(f"No dividend history available to plot for {ticker.upper()}.")

def analyze_stock_dictionary(stock_symbols):
    """
    Takes a list or dict keys, analyzes them, and returns a ranked leaderboard.
    """
    print("\nProcessing batch analysis...")
    results = {}

    for symbol in stock_symbols:
        try:
            data, dividends = get_data(symbol)
            # Skip if company doesn't pay a dividend
            if data.get("dividendYield") is None:
                continue

            is_sustainable, score, yield_val, metrics = analyze_dividend_sustainability(data, dividends)

            results[symbol] = {
                "Yield (%)": round(yield_val * 100, 2),
                "Score": score,
                "Status": "Sustainable" if is_sustainable else "Risky",
                "Metrics": metrics
            }
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    # Sort results by score descending
    sorted_results = dict(sorted(results.items(), key=lambda item: item[1]['Score'], reverse=True))

    # Print Leaderboard
    print("\n" + "="*55)
    print(f"{'Ticker':<10} | {'Yield (%)':<10} | {'Score':<10} | {'Status':<15}")
    print("="*55)
    for sym, info in sorted_results.items():
        print(f"{sym.upper():<10} | {info['Yield (%)']:<10} | {info['Score']:<10} | {info['Status']:<15}")
    print("="*55)

    return sorted_results

# ==========================================
# Example Usage:
# ==========================================
if __name__ == "__main__":
    # 1. Single analysis with plot
    analyze_and_plot("SWKS")

    # 2. Batch comparison
    portfolio = ["OCSL", "SWKS", "O", "T", "AAPL", "MO"]
    rankings = analyze_stock_dictionary(portfolio)

    print(rankings)

# BKGL, BREMI, CEIX, CHRD, CVX, DEZDE, DINO, DOX, EVOST, FAST, FHI, GFI, GFRDL, GILDE, GRMN, GTTPA, HL80F, HP, MED, MUR, NTES, OPRA, ORKOL, PR, PXD, REPMC, RIO, SCRPA, SKFBST, SWKS, SZUDE, VLO, WRT1VHE, XOM
