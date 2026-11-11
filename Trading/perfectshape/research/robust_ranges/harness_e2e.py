"""End-to-end: what a lagged dashboard scan lists, and how its ranges did in the final test (fixed scan-window band).

Per sector and scan end: the real pipeline.scan on prices up to the scan end (dashboard defaults: one window,
21-bar holdout, ranking / thinning), robust ranges off and on; then every listed range is traded with the band
of the window that described it, from the scan end over the next F bars (Trade Lab final-test rules).
"""
from __future__ import annotations

import time
from datetime import date

import numpy as np
import pandas as pd

from harness import HERE, simulate, load_all, crossings
from perfectshape.config import RunConfig
from perfectshape.data.panel import Panel
from perfectshape.holdings import SECTOR_ETFS, holdings
from perfectshape.pipeline import scan
from perfectshape.shapes import range_band

BASE = {
    "config_version": 1, "name": "e2e",
    "universe": {"tickers": ["X"]},
    "data": {"source": "yfinance", "years": 11},
    "search": {"mode": "ratio", "shapes": ["range"], "windows": [2520], "holdout_bars": 21},
    "ratio": {"k": 3, "allow_overlap": False, "keep_per_window": 300, "max_ratios": 25_000_000},
    "scoring": {"space": "log", "threshold": 0.6, "min_annual_return": 0.05, "min_range_height": 0.10,
                "max_range_drift": 0.5, "complexity_penalty": 0.0, "range_band_pct": 10, "range_exit": "mid",
                "range_harvest_scale": 0.15, "range_pain_scale": 2.0, "range_segments": 4, "range_speed_days": 0},
    "ranking": {"top_n": 30, "require_alive": True, "max_overlap": 0.5, "max_per_member": 3,
                "range_sort": "score", "range_min_held": 504, "range_min_score_window": 252},
}


def run(panel, sector, asof_idx, W, F, n_stocks, robust, k=3, pct=10):
    hold = 21
    start = asof_idx - W - hold + 1
    stop = asof_idx + F + 1
    if start < 0 or stop > panel.n_bars:
        return None
    order = [h.ticker for h in holdings(sector, today=date(2026, 11, 11))]
    sym = {s: i for i, s in enumerate(panel.symbols)}
    block = panel.close[start:stop]
    ok = np.isfinite(block).all(0) & (block > 0).all(0)
    cols = [sym[t] for t in order if t in sym and ok[sym[t]]][:n_stocks]
    if len(cols) < 2 * k + 2:
        return None
    syms = [panel.symbols[c] for c in cols]
    sub = Panel(panel.dates[start:asof_idx + 1], syms, panel.close[start:asof_idx + 1][:, cols])
    cfg = dict(BASE)
    cfg = {**BASE, "universe": {"tickers": syms}, "search": {**BASE["search"], "windows": [W]},
           "ratio": {**BASE["ratio"], "k": k},
           "scoring": {**BASE["scoring"], "range_robust": robust, "range_band_pct": pct}}
    out = scan(RunConfig.model_validate(cfg), panel=sub)
    res = out.ranked.get("range", [])
    full = panel.close[start:stop][:, cols]
    loc = {s: i for i, s in enumerate(syms)}
    rows = []
    for rank, r in enumerate(res, 1):
        b = r.basket
        fe = r.fit_end                       # row in sub (exclusive end of the fitted window)
        s0 = fe - r.ref_window
        X = full[s0:] / full[s0]
        N = X[:, [loc[m] for m in b.members]].mean(1)
        D = X[:, [loc[m] for m in b.den_members]].mean(1)
        Y = np.log(N) - np.log(D)
        lo, mid, hi = range_band(Y[:r.ref_window], pct)
        a = asof_idx - start - s0            # scan end row in Y
        sim = simulate(Y[a:a + F + 1, None], N[a:a + F + 1, None], D[a:a + F + 1, None],
                       np.array([lo]), np.array([mid]), np.array([hi]))
        sim1 = simulate(Y[a:a + F // 2 + 1, None], N[a:a + F // 2 + 1, None], D[a:a + F // 2 + 1, None],
                        np.array([lo]), np.array([mid]), np.array([hi]))
        half = (hi - lo) / 2
        Yf = Y[a + 1:a + F + 1]
        rows.append({"sector": sector, "asof": str(panel.dates[asof_idx]), "robust": robust, "rank": rank,
                     "num": " ".join(b.members), "den": " ".join(b.den_members), "score": r.score,
                     "ref": r.ref_window, **{k_: v for k_, v in r.metrics.items()},
                     "f2_n": int(sim["n_closed"][0]), "f2_ret": float(sim["ret"][0]),
                     "f2_open": int(sim["was_open"][0]), "f2_mdd": float(sim["mdd"][0]),
                     "f1_n": int(sim1["n_closed"][0]), "f1_ret": float(sim1["ret"][0]),
                     "f2_max_out": float(np.maximum(np.maximum(lo - Yf, Yf - hi), 0).max() / half),
                     "f2_cross": int(crossings(Yf[:, None], mid)[0]), "n_stocks": len(cols)})
    return rows


def main(W=2520, F=504, n=20, out="e2e.pkl", sectors=None, k=3, pct=10):
    panel = load_all()
    allrows = []
    t0 = time.time()
    for sector in sectors or SECTOR_ETFS:
        for a in pd.date_range("2015-01-01", "2024-11-08", freq="6MS"):
            ai = int(np.searchsorted(panel.dates, np.datetime64(a.date(), "D"), side="right") - 1)
            msg = []
            for robust in (False, True):
                rows = run(panel, sector, ai, W, F, n, robust, k=k, pct=pct)
                if rows is None:
                    break
                allrows += rows
                d = pd.DataFrame(rows)
                s = ((d.f2_n >= 2) & (d.f2_ret > 0)).mean() if len(d) else float("nan")
                msg.append(f"{'robust' if robust else 'plain'} {len(d)} listed succ {s:.2f}")
            if msg:
                print(f"{sector} {a.date()}: " + " | ".join(msg) + f" ({time.time() - t0:.0f}s)", flush=True)
                pd.DataFrame(allrows).to_pickle(HERE / out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--W", type=int, default=2520)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--pct", type=float, default=10)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--sectors", default="")
    ap.add_argument("--out", default="e2e.pkl")
    a = ap.parse_args()
    main(W=a.W, n=a.n, out=a.out, sectors=[s for s in a.sectors.split(",") if s] or None, k=a.k, pct=a.pct)
