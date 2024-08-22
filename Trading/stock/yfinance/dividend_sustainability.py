import yfinance as yf
import matplotlib.pyplot as plt
from Trading.symbols.google_search_symbol import get_yfinance_symbol_url
from Trading.symbols.constants import YAHOO_STOCK_SYMBOLS_DICT


def plot_dividend_growth(symbol, dividends):
    plt.figure(figsize=(10, 6))
    plt.plot(dividends.index, dividends.values, marker="o", linestyle="-")
    plt.title(f"Dividend Growth Over Time for {symbol}")
    plt.xlabel("Year")
    plt.ylabel("Dividend ($)")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def get_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.info, stock.dividends


def analyze_dividend_sustainability(data, should_print: bool = False):
    try:
        # Basic thresholds
        max_payout_ratio = 80  # Maximum payout ratio
        min_yield = 2.0  # Minimum dividend yield
        max_debt_equity = 0.5  # Maximum debt-to-equity ratio
        min_roe = 10.0  # Minimum Return on Equity
        min_free_cashflow = 1e7  # Minimum free cash flow

        # Data extraction
        payout_ratio = data["payoutRatio"] * 100
        dividend_yield = data["dividendYield"] * 100
        debt_equity = data["debtToEquity"] / 100.0
        roe = data["returnOnEquity"] * 100
        free_cashflow = data["freeCashflow"]

        if should_print:
            print("--------------------")
            print(f"Payout ratio: {payout_ratio:.2f}%")
            print(f"Dividend yield: {dividend_yield:.2f}%")
            print(f"Debt-to-equity ratio: {debt_equity:.2f}")
            print(f"Return on equity: {roe:.2f}%")
            print(
                f"Free cash flow divided by min cash flow: {free_cashflow / min_free_cashflow:.2f}"
            )

        from Trading.utils.criterion.expression import Numerical, and_
        import operator

        payout_criterion = Numerical(
            "Payout ratio", operator.lt, payout_ratio, max_payout_ratio
        )
        yield_criterion = Numerical(
            "Dividend yield", operator.ge, dividend_yield, min_yield
        )
        debt_criterion = Numerical(
            "Debt-to-equity ratio", operator.le, debt_equity, max_debt_equity
        )
        roe_criterion = Numerical("Return on equity", operator.ge, roe, min_roe)
        free_cashflow_criterion = Numerical(
            "Free cash flow", operator.ge, free_cashflow, min_free_cashflow
        )
        criteria = and_(
            payout_criterion,
            yield_criterion,
            debt_criterion,
            roe_criterion,
            free_cashflow_criterion,
        )
        print(criteria.formatted())

        if criteria.evaluate():
            return True, "The stock is worth considering for dividend sustainability."
        else:
            return (
                False,
                "The stock does not meet the dividend sustainability criteria.",
            )
    except KeyError:
        return False, "Not all necessary data is available to evaluate the stock."


def analyze_and_plot(symbol_to_find: str):
    # Example usage
    ticker, _ = get_yfinance_symbol_url(
        symbol_to_find
    )  # use the ticker symbol of the stock you want to analyze
    data, dividends = get_data(str(ticker))

    is_sustainable, message = analyze_dividend_sustainability(data, should_print=True)
    print(f"{ticker}: {message}")

    # Filter dividends for the last 10 years
    last_10_years_dividends = dividends.last("10Y")

    # Plotting the dividend history of the last 10 years
    plot_dividend_growth(ticker, last_10_years_dividends)
    # MED, RAND, IIPR, MO, DOC, UMC, KEY are good examples


# Example: analyze_and_plot("crescent capital")


def get_sustainable_dividend_stocks():
    sustainable_dividend_stocks = []
    for d in YAHOO_STOCK_SYMBOLS_DICT:
        yahoo_stock_symbol = YAHOO_STOCK_SYMBOLS_DICT[d][0]
        data, dividends = get_data(yahoo_stock_symbol)
        is_sustainable, message = analyze_dividend_sustainability(data)
        if is_sustainable:
            sustainable_dividend_stocks.append(d)
            print(f"{yahoo_stock_symbol}: {message}")
    return sustainable_dividend_stocks


sustainable_dividend_stocks = ["OCSL", "swks"]
print(sustainable_dividend_stocks)
for s in sustainable_dividend_stocks:
    analyze_and_plot(s)

# CEIX, CHRD, CVX!!, DINO, GIL.DE, HF Sinclair Corporation, REP.MC, swks!
# RIO TINTO TO ADD
# TO LOOK: swks

# sustainable_dividend_stocks = ['BEKB.BR',
# 'BKG.L',
# 'BRE.MI',
# 'CEIX',
# 'CHRD',
# 'CVX',
# 'DEZ.DE',
# 'DINO',
# 'DOX',
# 'EVO.ST',
# 'FAST',
# 'FHI',
# 'GFI',
# 'GFRD.L',
# 'GIL.DE',
# 'GRMN',
# 'GTT.PA',
# 'HL80.F',
# 'HP',
# 'MED',
# 'MUR',
# 'NTES',
# 'OPRA',
# 'ORK.OL',
# 'PR',
# 'PXD',
# 'REP.MC',
# 'RIO',
# 'SCR.PA',
# 'SKF-B.ST',
# 'SWKS',
# 'SZU.DE',
# 'VLO',
# 'WRT1V.HE',
# 'XOM']
