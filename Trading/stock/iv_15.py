import yfinance as yf
import pandas as pd

def calculate_iv15_tragic_algebra(ticker_symbol, growth_rate=0.15, terminal_multiple=15, manual_sbc=None):
    """
    Calculates the IV15 with adjustments for 'The Tragic Algebra'.
    Handles missing data (NaN) gracefully and allows manual SBC overrides.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)

        # 1. Get current price and shares outstanding
        info = ticker.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        shares = info.get('sharesOutstanding')

        if not current_price or not shares:
            return f"Error: Could not retrieve price or share count for {ticker_symbol}."

        # 2. Get Cash Flow Data
        cf = ticker.cash_flow

        # Calculate Base FCF
        if 'Free Cash Flow' in cf.index:
            base_fcf = cf.loc['Free Cash Flow'].iloc[0]
        elif 'Operating Cash Flow' in cf.index and 'Capital Expenditure' in cf.index:
            base_fcf = cf.loc['Operating Cash Flow'].iloc[0] + cf.loc['Capital Expenditure'].iloc[0]
        else:
            return f"Error: Could not retrieve Free Cash Flow data for {ticker_symbol}."

        if pd.isna(base_fcf):
            return f"Error: Base FCF data is missing (NaN) for {ticker_symbol}."

        # 3. Apply the 'Tragic Algebra' Adjustment (Deduct SBC)
        sbc = 0

        if manual_sbc is not None:
            sbc = manual_sbc
        elif 'Stock Based Compensation' in cf.index:
            sbc_value = cf.loc['Stock Based Compensation'].iloc[0]
            # Safely check if the API returned a NaN value
            if not pd.isna(sbc_value):
                sbc = abs(sbc_value)

        true_fcf = base_fcf - sbc

        if pd.isna(true_fcf) or true_fcf <= 0:
            return f"Error: {ticker_symbol} has negative True FCF after deducting ${sbc/1e9:.2f}B in SBC."

        # 4. Project True Cash Flows for 15 Years
        future_cash_flows = []
        projected_fcf = true_fcf
        for _ in range(1, 16):
            projected_fcf *= (1 + growth_rate)
            future_cash_flows.append(projected_fcf)

        # 5. Calculate Terminal Value (Year 15)
        terminal_value = future_cash_flows[-1] * terminal_multiple

        # 6. Discount back to Present Value at the strict 15% hurdle rate
        discount_rate = 0.15
        pv_of_cash_flows = sum(fcf / ((1 + discount_rate) ** i) for i, fcf in enumerate(future_cash_flows, 1))
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** 15)

        total_intrinsic_value = pv_of_cash_flows + pv_of_terminal_value

        # 7. Calculate IV15 Per Share and Ratios
        iv15_price = total_intrinsic_value / shares
        price_to_iv15 = current_price / iv15_price

        return {
            "Ticker": ticker_symbol.upper(),
            "Current Price": f"${current_price:.2f}",
            "Reported FCF": f"${base_fcf / 1e9:.2f} Billion",
            "Stock-Based Comp": f"${sbc / 1e9:.2f} Billion" + (" (Manual Override)" if manual_sbc else ""),
            "Adjusted True FCF": f"${true_fcf / 1e9:.2f} Billion",
            "Calculated IV15": f"${iv15_price:.2f}",
            "Price / IV15": round(price_to_iv15, 2)
        }

    except Exception as e:
        return f"An error occurred: {e}"

# Example Usage:
if __name__ == "__main__":
    # Test MELI. If the API fails to find SBC, it will default to $0 Billion.# $303 Million is passed as 303,000,000
    result = calculate_iv15_tragic_algebra("MELI", growth_rate=0.20, terminal_multiple=20, manual_sbc=303000000)
    for key, value in result.items():
        print(f"{key}: {value}")

    print("\n--- Testing with Manual Override ---\n")

    # Example: Manually passing in $200 million for SBC (entered as 200,000,000)
    result_manual = calculate_iv15_tragic_algebra("MELI", growth_rate=0.20, terminal_multiple=20, manual_sbc=200000000)
    for key, value in result_manual.items():
        print(f"{key}: {value}")
