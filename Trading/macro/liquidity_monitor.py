import os
import pandas as pd
from fredapi import Fred
from datetime import datetime, timedelta

class LiquidityMonitor:
    def __init__(self, api_key):
        """Initialize the FRED API connection."""
        self.fred = Fred(api_key=api_key)
        # Lookback period of 1 year to calculate trends
        self.start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    def fetch_data(self):
        """Fetch the necessary economic series from FRED."""
        print("Fetching data from FRED...")
        try:
            self.walcl = self.fred.get_series('WALCL', observation_start=self.start_date)
            self.rrp = self.fred.get_series('RRPONTSYD', observation_start=self.start_date)
            self.yield_spread = self.fred.get_series('T10Y2Y', observation_start=self.start_date)
            self.stress_index = self.fred.get_series('STLFSI4', observation_start=self.start_date)
            print("Data fetched successfully.\n")
        except Exception as e:
            print(f"Error fetching data: {e}", flush=True)
            raise

    def calculate_score(self):
        """
        Calculates a 0-100 probability score of a liquidity crisis.
        Each of the 4 metrics contributes up to 25 points to the risk profile.
        """
        score = 0
        details = []

        # 1. Reverse Repo Facility (RRPONTSYD) - 25 points max
        # RRP is the excess liquidity buffer. If it's near 0, the buffer is gone.
        current_rrp = self.rrp.iloc[-1]
        # Assuming < $500B is the danger zone where reserves might get tight
        rrp_score = max(0, min(25, 25 * (1 - (current_rrp / 500))))
        score += rrp_score
        details.append(f"RRP Level: ${current_rrp:,.2f}B -> Risk Score: {rrp_score:.1f}/25")

        # 2. Financial Stress Index (STLFSI4) - 25 points max
        # Normal is 0. Anything above 1 signifies extreme stress.
        current_stress = self.stress_index.iloc[-1]
        stress_score = max(0, min(25, current_stress * 15))
        score += stress_score
        details.append(f"Financial Stress Index: {current_stress:.4f} -> Risk Score: {stress_score:.1f}/25")

        # 3. Fed Balance Sheet (WALCL) - 25 points max
        # We look at the 1-year rate of change (Quantitative Tightening speed)
        current_walcl = self.walcl.iloc[-1]
        year_ago_walcl = self.walcl.iloc[0]
        yoy_change_pct = ((current_walcl - year_ago_walcl) / year_ago_walcl) * 100
        # If it's shrinking faster than 5% YoY, that's high liquidity drain
        walcl_score = 0 if yoy_change_pct > 0 else min(25, max(0, abs(yoy_change_pct) * 2))
        score += walcl_score
        details.append(f"Balance Sheet YoY Change: {yoy_change_pct:.2f}% -> Risk Score: {walcl_score:.1f}/25")

        # 4. Yield Curve Spread (T10Y2Y) - 25 points max
        # Risk is highest when the curve is deeply inverted (< -0.5) OR
        # when it rapidly un-inverts back to positive after a long inversion.
        current_spread = self.yield_spread.iloc[-1]
        six_mo_spread = self.yield_spread.iloc[-126] # approx 6 months ago trading days

        if current_spread < -0.50:
            spread_score = 25 # Deep inversion
        elif current_spread < 0:
            spread_score = 15 # Mild inversion
        elif current_spread > 0 and six_mo_spread < 0:
            spread_score = 20 # Rapid un-inversion (the "bear steepener" danger zone)
        else:
            spread_score = 0  # Normal upward sloping curve

        score += spread_score
        details.append(f"10Y-2Y Spread: {current_spread:.2f}% -> Risk Score: {spread_score:.1f}/25")

        return score, details

    def run_analysis(self):
        """Execute the full pipeline and print the report."""
        self.fetch_data()
        total_score, breakdown = self.calculate_score()

        print("="*50)
        print(" LIQUIDITY CRISIS PROBABILITY REPORT")
        print("="*50)
        for item in breakdown:
            print(f"• {item}")
        print("-" * 50)
        print(f"OVERALL CRISIS PROBABILITY (Next 30 Days): {total_score:.1f}%")
        print("="*50)

        # Basic Interpretation
        if total_score < 30:
            print("Status: GREEN. Systemic liquidity is abundant. Low risk of immediate crisis.")
        elif total_score < 60:
            print("Status: YELLOW. Liquidity buffers are normalizing or tightening. Monitor closely.")
        elif total_score < 80:
            print("Status: ORANGE. Plumbing is highly stressed. Repo spikes or shadow banking issues likely.")
        else:
            print("Status: RED. High probability of systemic liquidity breaking. Fed intervention likely needed.")

if __name__ == "__main__":
    API_KEY = os.environ["FRED_API_KEY"]

    monitor = LiquidityMonitor(api_key=API_KEY)
    monitor.run_analysis()
