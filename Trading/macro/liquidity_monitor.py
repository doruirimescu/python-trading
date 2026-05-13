import json
import os
import warnings
import numpy as np
import pandas as pd
from fredapi import Fred
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Component registry
#
# direction='positive' : high values  → high stress  (z-score kept as-is)
# direction='negative' : low  values  → high stress  (series negated before z-scoring)
# weight               : must sum to 1.0 across all entries
#
# Scoring convention: 50 = historically neutral (z=0)
#                    100 = extreme stress  (+3σ)
#                      0 = extreme accommodation (−3σ)
# ---------------------------------------------------------------------------
COMPONENTS = {
    # --- overnight money-market plumbing ---
    'SOFR_FF':   {'desc': 'SOFR − FF Spread (%)',           'direction': 'positive', 'weight': 0.15},
    'WRESBAL':   {'desc': 'Bank Reserve Balances ($B)',      'direction': 'negative', 'weight': 0.15},
    # --- broad stress / excess-liquidity buffer ---
    'STLFSI4':   {'desc': 'Financial Stress Index',          'direction': 'positive', 'weight': 0.12},
    'RRPONTSYD': {'desc': 'Overnight RRP ($B)',              'direction': 'negative', 'weight': 0.12},
    # --- structural / QE-QT ---
    'T10Y2Y':    {'desc': '10Y − 2Y Yield Spread (%)',       'direction': 'negative', 'weight': 0.10},
    'WALCL_YOY': {'desc': 'Fed Balance Sheet YoY (%)',       'direction': 'negative', 'weight': 0.10},
    # --- fiscal / TGA drain ---
    'WDTGAL':    {'desc': 'Treasury Gen. Account ($B)',      'direction': 'positive', 'weight': 0.08},
    # --- market volatility proxy (MOVE not in FRED) ---
    'VIXCLS':    {'desc': 'VIX (MOVE proxy)',                'direction': 'positive', 'weight': 0.08},
    # --- bank credit / term funding risk ---
    'TEDRATE':   {'desc': 'TED Spread / FRA-OIS proxy (%)', 'direction': 'positive', 'weight': 0.05},
    # --- bill market / repo collateral pressure ---
    'DTB3_SOFR': {'desc': '3M T-Bill − SOFR (%)',            'direction': 'negative', 'weight': 0.05},
}

# Indicators the user requested that are not publicly available in FRED
_NOT_IN_FRED = [
    'MOVE index (bond vol)        — VIX used as proxy; MOVE not in FRED',
    'Cross-currency basis          — requires Bloomberg / Refinitiv',
    '  (EURUSD, JPYUSD basis swaps)',
    'GC repo specials / repo fails — primary dealer survey, not in FRED',
]


class LiquidityStressMonitor:
    LOOKBACK_DAYS = 1095   # 3 yr fetch window; z-score needs ~504 bdays for WALCL_YOY
    ZSCORE_WINDOW = 252    # 1 trading year rolling window
    ZSCORE_CAP    = 3.0    # cap tails at ±3σ so single outliers don't dominate

    _FRED_IDS = (
        'WALCL', 'RRPONTSYD', 'T10Y2Y', 'STLFSI4',
        'SOFR', 'DFF', 'WRESBAL', 'WDTGAL', 'VIXCLS', 'TEDRATE', 'DTB3',
    )

    def __init__(self, api_key):
        self.fred = Fred(api_key=api_key)
        self.start_date = (datetime.now() - timedelta(days=self.LOOKBACK_DAYS)).strftime('%Y-%m-%d')
        self._raw = {}

    # ------------------------------------------------------------------
    # Data layer
    # ------------------------------------------------------------------
    def fetch_data(self):
        print('Fetching data from FRED...')
        for sid in self._FRED_IDS:
            try:
                self._raw[sid] = self.fred.get_series(sid, observation_start=self.start_date)
                print(f'  ok  {sid}')
            except Exception as exc:
                warnings.warn(f'Could not fetch {sid}: {exc}')
        print()

    def _bday(self, s):
        """Resample any FRED frequency to business-day grid, forward-filling gaps."""
        if s.empty:
            return s
        if not isinstance(s.index, pd.DatetimeIndex):
            s = s.copy()
            s.index = pd.to_datetime(s.index)
        return s.resample('B').last().ffill()

    def build_components(self):
        """Construct all indicator series, aligned to a common business-day index."""
        r = {k: self._bday(v) for k, v in self._raw.items()}
        out = {}

        # --- direct pass-throughs ---
        for key in ('STLFSI4', 'RRPONTSYD', 'T10Y2Y', 'WRESBAL', 'WDTGAL', 'VIXCLS'):
            if key in r:
                out[key] = r[key]

        # TED spread: historical FRA-OIS proxy (FRED discontinued May 2023; NaN after)
        if 'TEDRATE' in r:
            out['TEDRATE'] = r['TEDRATE']

        # SOFR − FF: overnight repo vs administered fed-funds rate
        # SOFR > DFF means repo markets are tight relative to policy intent → stress
        if 'SOFR' in r and 'DFF' in r:
            out['SOFR_FF'] = r['SOFR'] - r['DFF']

        # 3M T-Bill − SOFR: bill scarcity / collateral stress signal
        # Negative (bills yield less than overnight cash) → demand for safe collateral → stress
        if 'DTB3' in r and 'SOFR' in r:
            out['DTB3_SOFR'] = r['DTB3'] - r['SOFR']

        # Fed balance sheet 1-yr % change: captures QT drain speed
        # Shrinking balance sheet (negative YoY) → liquidity withdrawal → stress
        if 'WALCL' in r:
            out['WALCL_YOY'] = r['WALCL'].pct_change(252) * 100

        return out

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _zscore_stress(self, s):
        """
        Rolling z-score with capped tails, mapped to [0, 100].
        Uses 252-day window; requires ≥126 observations (6 months) to produce a value.
        """
        w = self.ZSCORE_WINDOW
        mu  = s.rolling(w, min_periods=w // 2).mean()
        sig = s.rolling(w, min_periods=w // 2).std()
        z = (s - mu) / sig.replace(0, np.nan)
        return (z.clip(-self.ZSCORE_CAP, self.ZSCORE_CAP) + self.ZSCORE_CAP) / (2 * self.ZSCORE_CAP) * 100

    def calculate_composite(self, components):
        scores = {}

        for key, cfg in COMPONENTS.items():
            s = components.get(key)
            if s is None or s.dropna().empty:
                continue

            # negate 'negative'-direction series so that low value → high z → high stress
            signed = s if cfg['direction'] == 'positive' else -s
            scored = self._zscore_stress(signed)
            if scored.empty:
                continue
            current = scored.iloc[-1]

            if np.isnan(current):
                continue

            scores[key] = {
                'desc':   cfg['desc'],
                'weight': cfg['weight'],
                'score':  current,
                'value':  s.iloc[-1],
            }

        total_w = sum(v['weight'] for v in scores.values())
        if not total_w:
            raise RuntimeError('No valid indicators — check FRED connectivity.')

        # renormalize weights in case some series were unavailable
        composite = sum(v['score'] * v['weight'] / total_w for v in scores.values())
        return composite, scores, total_w

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    def run_analysis(self):
        self.fetch_data()
        components = self.build_components()
        composite, breakdown, used_w = self.calculate_composite(components)
        self.liquidity_stress_score = composite
        self._breakdown = breakdown

        W = 64
        date_str = datetime.now().strftime('%Y-%m-%d')
        print('=' * W)
        print(f'  LIQUIDITY STRESS MONITOR  —  {date_str}')
        print('=' * W)
        print(f'  Composite Liquidity Stress Score:  {composite:5.1f} / 100')
        if used_w < 0.95:
            print(f'  (running on {used_w*100:.0f}% of target weight — some series unavailable)')
        print()
        print(f"  {'Indicator':<36} {'Score':>6}  {'Wgt':>4}   Current")
        print('-' * W)

        for v in sorted(breakdown.values(), key=lambda x: -x['score']):
            print(f"  {v['desc']:<36} {v['score']:>5.1f}  {v['weight']*100:>3.0f}%  {v['value']:>10.3f}")

        print('-' * W)
        print()
        print('  Indicators not available in FRED (external data required):')
        for note in _NOT_IN_FRED:
            print(f'    {note}')

        print()
        print('  Note: T10Y2Y scored on level only. Bear-steepener stress (rapid')
        print('  un-inversion after prolonged inversion) is not captured by z-score')
        print('  of level alone — add a 6M momentum series if needed.')
        print()
        print('  Note: TED spread (FRA-OIS proxy) was discontinued by FRED in May 2023.')
        print('  Post-2023 values will be NaN and the weight redistributed automatically.')
        print()
        print('=' * W)

        if composite < 25:
            label = 'GREEN    — Systemic liquidity abundant. Low near-term risk.'
        elif composite < 45:
            label = 'YELLOW   — Conditions tightening. Monitor closely.'
        elif composite < 65:
            label = 'ORANGE   — Plumbing under stress. Repo / shadow-banking strain likely.'
        elif composite < 80:
            label = 'RED      — Acute stress. Fed emergency facility probable.'
        else:
            label = 'CRITICAL — Systemic breakdown imminent. Immediate intervention needed.'

        print(f'  Status: {label}')
        print('=' * W)

    def save_results(self, output_path: str) -> Path:
        """Serialize the latest composite score and component breakdown to JSON.

        Creates parent directories if needed.  Returns the path written.
        Call after run_analysis().
        """
        date_str = datetime.now().strftime('%Y-%m-%d')
        dest = Path(output_path) / f'liquidity_stress_{date_str}.json'
        dest.parent.mkdir(parents=True, exist_ok=True)

        composite = self.liquidity_stress_score
        if composite < 25:
            status = 'GREEN'
        elif composite < 45:
            status = 'YELLOW'
        elif composite < 65:
            status = 'ORANGE'
        elif composite < 80:
            status = 'RED'
        else:
            status = 'CRITICAL'

        payload = {
            'date': date_str,
            'liquidity_stress_score': round(composite, 2),
            'status': status,
            'components': {
                key: {
                    'desc':   v['desc'],
                    'score':  round(v['score'], 2),
                    'weight': v['weight'],
                    'value':  round(v['value'], 4),
                }
                for key, v in self._breakdown.items()
            },
        }

        with open(dest, 'w') as f:
            json.dump(payload, f, indent=2)

        print(f'Results saved to {dest}')
        return dest


if __name__ == '__main__':
    API_KEY = os.environ['FRED_API_KEY']
    LiquidityStressMonitor(api_key=API_KEY).run_analysis()
