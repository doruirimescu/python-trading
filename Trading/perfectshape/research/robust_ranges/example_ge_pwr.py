"""One listed range that broke: XLI, GE DE ETN / PWR UPS DAL, 10-year window, scan end 2025-05 (lag 1.5 years).

Its gates, how its fixed-share legs drifted, which stock moved the final test, and what stops would have done.
Uses the project's data_cache (DAL is not in this folder's cache)."""
import sys
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))
from perfectshape.config import DataConfig, ScoringConfig  # noqa: E402
from perfectshape.data.panel import align  # noqa: E402
from perfectshape.data.sources import load_yfinance  # noqa: E402
from perfectshape.shapes import get_shape, range_band  # noqa: E402
from stops import sim  # noqa: E402

NUM, DEN = ["GE", "DE", "ETN"], ["PWR", "UPS", "DAL"]
cfg_d = DataConfig(source="yfinance", years=12, cache_dir=str(HERE.parents[1] / "data_cache"), max_age_days=3650)
p = align(load_yfinance(NUM + DEN, cfg_d, today=date(2026, 11, 11)), max_gap_bars=3)
C = p.close[:, [p.symbols.index(t) for t in NUM + DEN]]
end = int(np.searchsorted(p.dates, np.datetime64("2025-05-11"), side="right") - 1)   # scan end
W = 2520
s0 = end - 21 + 1 - W                                                                   # 21-bar holdout
X = C[s0:] / C[s0]
N, D = X[:, :3].mean(1), X[:, 3:].mean(1)
Y = np.log(N) - np.log(D)
a = end - s0
print(f"window {p.dates[s0]} -> {p.dates[s0 + W - 1]}, scan end {p.dates[end]}, last {p.dates[-1]}")

cfg = ScoringConfig(threshold=0.6, min_annual_return=0.05, min_range_height=0.10, complexity_penalty=0.0, range_robust=True)
res = get_shape("range").score((N / D)[:W, None] / (N / D)[0], cfg)
m = {k: round(float(v[0]), 3) for k, v in res.metrics.items()}
print(f"robust score {float(res.score[0]):.3f}: trades/yr {m['trades_per_year']} (gate >= 1.5), band/vol {m['band_vol']} "
      f"(<= 0.45), recent vol {m['recent_vol']} (>= 1.0)")

print("\nmember growth over the window and its drifted weight in the leg at the scan end:")
for j, t in enumerate(NUM + DEN):
    leg = slice(0, 3) if j < 3 else slice(3, 6)
    print(f"  {t:4s} x{X[W - 1, j]:5.2f}  weight {X[a, j] / X[a, leg].sum():.2f}  final-test move {X[-1, j] / X[a, j] - 1:+.0%}")
print(f"final test: ratio {np.exp(Y[-1] - Y[a]) - 1:+.1%} (numerator leg {N[-1] / N[a] - 1:+.1%}, "
      f"denominator leg {D[-1] / D[a] - 1:+.1%}), low {np.exp(Y[a:].min() - Y[a]) - 1:+.1%}")

lo, _, hi = range_band(Y[:W], 10)
half = (hi - lo) / 2
print(f"\nband {np.exp(lo):.3f}-{np.exp(hi):.3f}; window extremes {(lo - Y[:W].min()) / half:.2f} / "
      f"{(Y[:W].max() - hi) / half:.2f} half-bands beyond the edges; final-test low {(lo - Y[a + 1:].min()) / half:.1f} below")
for nm, kw in (("no stop", {}), ("stop 10%", {"stop": .10}), ("stop 20%", {"stop": .20}),
               ("window-extreme stop", {"brk_lo": Y[:W].min(), "brk_hi": Y[:W].max()})):
    r = sim(Y[a:], N[a:], D[a:], lo, hi, **kw)
    print(f"  {nm:20s} P&L {r['ret']:+.1%}  reversions {r['n_med']}")
