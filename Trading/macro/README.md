# Macro — Liquidity Stress Monitor

A composite, regime-agnostic indicator that scores US systemic liquidity conditions on a **0–100 scale**, where 50 is historically neutral and 100 is extreme stress.

## What it does

`LiquidityStressMonitor` pulls eleven time series from the FRED API, constructs ten stress components (some raw, some derived), standardises each via a **1-year rolling z-score**, caps the tails at ±3σ, and combines them into a single weighted composite.

The score is emailed monthly via `run_monthly_analysis.py`.

## Scoring convention

| Score | Status | Interpretation |
|---|---|---|
| < 25 | GREEN | Systemic liquidity abundant, low near-term risk |
| 25–44 | YELLOW | Conditions tightening, monitor closely |
| 45–64 | ORANGE | Plumbing under stress, repo / shadow-banking strain likely |
| 65–79 | RED | Acute stress, Fed emergency facility probable |
| ≥ 80 | CRITICAL | Systemic breakdown imminent |

## Components

Each component is standardised independently via a 252-bday rolling z-score, then mapped to [0, 100]. Weights are renormalised at runtime if a series is unavailable.

| Key | FRED series / derivation | Stress direction | Weight |
|---|---|---|---|
| `SOFR_FF` | SOFR − DFF (overnight repo vs fed funds) | positive | 15% |
| `WRESBAL` | Bank reserve balances at the Fed | negative (low = stress) | 15% |
| `STLFSI4` | St. Louis Fed Financial Stress Index | positive | 12% |
| `RRPONTSYD` | Overnight reverse repo (excess liquidity buffer) | negative | 12% |
| `T10Y2Y` | 10Y − 2Y yield spread | negative (inversion = stress) | 10% |
| `WALCL_YOY` | Fed balance sheet 1-yr % change (QT drain) | negative | 10% |
| `WDTGAL` | Treasury General Account balance | positive (high TGA drains reserves) | 8% |
| `VIXCLS` | VIX (rates-vol proxy — MOVE not in FRED) | positive | 8% |
| `TEDRATE` | TED spread (FRA-OIS proxy, discontinued May 2023) | positive | 5% |
| `DTB3_SOFR` | 3M T-Bill − SOFR (bill scarcity / collateral pressure) | negative | 5% |

**Not available in FRED** (would require Bloomberg / Refinitiv):
- MOVE index (bond implied vol)
- Cross-currency basis swaps (EURUSD, JPYUSD)
- GC repo specials / repo fails (primary dealer survey data)

## Known limitations

- **Bear-steepener risk**: `T10Y2Y` is scored on its level only. Rapid un-inversion after prolonged inversion (a classic precursor to credit stress) requires a separate 6M momentum series.
- **TED spread**: discontinued by FRED in May 2023. Its 5% weight is redistributed automatically across available components.
- **SOFR history**: available from April 2018 only, limiting z-score calibration to the post-LIBOR era.

## Setup

```bash
pip install fredapi pandas numpy
export FRED_API_KEY=<your_key>   # free at https://fred.stlouisfed.org/docs/api/api_key.html
```

## Usage

```python
from Trading.macro.liquidity_monitor import LiquidityStressMonitor

monitor = LiquidityStressMonitor(api_key=api_key)
monitor.run_analysis()

# Score is stored after run_analysis() for programmatic access
print(monitor.liquidity_stress_score)
```

Or run directly:

```bash
python -m Trading.macro.liquidity_monitor
```

Monthly email dispatch:

```bash
python Trading/macro/run_monthly_analysis.py
```
