"""Trend robustness study: in-sample features of the best uptrend ratios vs what the ratio did in the next 1-2 years."""
from __future__ import annotations

import time
from datetime import date

import numpy as np
import pandas as pd

from harness import HERE, PPY, SCORING, load_all
from perfectshape.data.panel import Panel
from perfectshape.holdings import SECTOR_ETFS, holdings
from perfectshape.ratio import search_ratio_window
from perfectshape.shapes import get_shape, linear_fit

UP = get_shape("uptrend")


def tfeatures(Y, N, D, spy, etf):
    W, m = Y.shape
    res = UP.score_y(Y, SCORING, full=True)
    f = {"score": res.score}
    f.update(res.metrics)
    a, b, resid, r2 = linear_fit(Y)
    slope = b / ((W - 1) / PPY)                       # log per year
    f["slope"] = slope
    dy = np.diff(Y, axis=0)
    vol = dy.std(0) * np.sqrt(PPY)
    f["vol"] = vol
    f["sharpe"] = slope / np.maximum(vol, 1e-12)
    f["resid_sd"] = resid.std(0) / np.maximum(np.abs(slope), 1e-12)   # years of trend
    f["end_resid"] = resid[-1] / np.maximum(resid.std(0), 1e-12)        # where it ends vs the line, in sd
    nb = 5
    bounds = np.linspace(0, W, nb + 1).astype(int)
    bs = []
    for s0, s1 in zip(bounds[:-1], bounds[1:]):
        bs.append((Y[s1 - 1] - Y[s0]) / ((s1 - s0) / PPY))
    bs = np.stack(bs)
    f["blk_min_slope"] = bs.min(0) / np.maximum(slope, 1e-12)
    f["blk_last_slope"] = bs[-1] / np.maximum(slope, 1e-12)
    f["blk_neg"] = (bs < 0).sum(0)
    f["blk_cv"] = bs.std(0) / np.maximum(np.abs(bs.mean(0)), 1e-12)
    # curvature: quadratic coefficient relative to the move (accelerating > 0, decelerating < 0)
    x = np.linspace(-1, 1, W)
    P = np.vander(x, 3, increasing=True)
    c = np.linalg.lstsq(P, Y, rcond=None)[0]
    f["curv"] = c[2] / np.maximum(np.abs(b), 1e-12)
    for L, nm in ((252, "r1"), (126, "r6m"), (63, "r3m")):
        f[f"ret_{nm}"] = (Y[-1] - Y[-L]) / (L / PPY) / np.maximum(slope, 1e-12)
    # recent r2 (last 2 years)
    _, _, _, r2r = linear_fit(Y[-504:], with_resid=False)
    f["r2_recent"] = r2r
    # walk-forward: line fitted on Y[:cut], did the next 2y keep rising?
    wf = []
    for frac in (0.4, 0.5, 0.6, 0.7, 0.8):
        cut = int(W * frac)
        wf.append((Y[cut + 503] - Y[cut - 1]) if cut + 504 <= W else np.full(m, np.nan))
    wf = np.stack(wf)
    f["wf_min"] = np.nanmin(wf, 0) / np.maximum(slope * 2, 1e-12)
    f["wf_pos"] = (wf > 0).mean(0)
    rn, rd = np.diff(np.log(N), axis=0), np.diff(np.log(D), axis=0)
    rnc, rdc = rn - rn.mean(0), rd - rd.mean(0)
    f["leg_corr"] = (rnc * rdc).sum(0) / np.sqrt((rnc ** 2).sum(0) * (rdc ** 2).sum(0))
    for nm, idx in (("spy", spy), ("etf", etf)):
        rs = np.diff(np.log(idx))
        rsc = rs - rs.mean()
        dyc = dy - dy.mean(0)
        f[f"beta_{nm}"] = (rsc @ dyc) / (rsc @ rsc)
        f[f"corr_{nm}"] = (rsc @ dyc) / np.sqrt((rsc @ rsc) * (dyc ** 2).sum(0))
    # one stock carrying the trend: share of the numerator's gain made by its best member
    return f


def run_one(panel, sector, asof_idx, W, F, k, n_stocks, keep):
    start, stop = asof_idx - W + 1, asof_idx + F + 1
    if start < 0 or stop > panel.n_bars:
        return None
    order = [h.ticker for h in holdings(sector, today=date(2026, 11, 11))]
    sym = {s: i for i, s in enumerate(panel.symbols)}
    block = panel.close[start:stop]
    ok = np.isfinite(block).all(0) & (block > 0).all(0)
    cols = [sym[t] for t in order if t in sym and ok[sym[t]]][:n_stocks]
    if len(cols) < 2 * k + 2:
        return None
    sub = Panel(panel.dates[start:stop], [panel.symbols[c] for c in cols], panel.close[start:stop][:, cols])
    from perfectshape.config import RatioConfig
    found = search_ratio_window(sub, UP, W, W, RatioConfig(k=k, keep_per_window=keep), SCORING)
    if not found:
        return None
    idx = {s: i for i, s in enumerate(sub.symbols)}
    num = np.array([[idx[s] for s in b.members] for b in found])
    den = np.array([[idx[s] for s in b.den_members] for b in found])
    X = sub.close / sub.close[0]
    N, D = X[:, num].mean(2), X[:, den].mean(2)
    Y = np.log(N) - np.log(D)
    spy = panel.close[start:stop, sym["SPY"]]
    etf = panel.close[start:stop, sym[sector]]
    f = tfeatures(Y[:W], N[:W], D[:W], spy[:W], etf[:W])
    a, b, resid, _ = linear_fit(Y[:W])
    slope_bar = b / (W - 1)
    lo_dev = resid.min(0)
    out = {}
    for H, tag in ((F, "f2"), (F // 2, "f1")):
        out[f"{tag}_ret"] = Y[W - 1 + H] - Y[W - 1]                     # log ratio move
        out[f"{tag}_vs_slope"] = out[f"{tag}_ret"] / np.maximum(slope_bar * H, 1e-12)
        # pair P&L long num / short den over the period
        n_, d_ = N[W - 1 + H] / N[W - 1], D[W - 1 + H] / D[W - 1]
        out[f"{tag}_pair"] = n_ - d_
    # channel: stays above the in-sample lower channel extended (like the alive check)
    t = np.arange(W, W + F)
    line = a[None, :] + slope_bar[None, :] * t[:, None]
    out["f2_below_channel"] = (Y[W:W + F] < line + lo_dev[None, :]).any(0).astype(int)
    out["f2_mdd"] = (np.maximum.accumulate(Y[W - 1:W + F], axis=0) - Y[W - 1:W + F]).max(0)
    df = pd.DataFrame({**f, **out})
    df.insert(0, "rank", np.arange(1, len(found) + 1))
    df.insert(0, "num", [" ".join(b.members) for b in found])
    df.insert(1, "den", [" ".join(b.den_members) for b in found])
    df.insert(0, "asof", str(panel.dates[asof_idx]))
    df.insert(0, "sector", sector)
    df["W"] = W
    return df


def main(W=2520, F=504, k=3, n=20, keep=200, out="trend.pkl", sectors=None):
    panel = load_all()
    frames = []
    t0 = time.time()
    for sector in sectors or SECTOR_ETFS:
        for a in pd.date_range("2015-01-01", "2024-11-08", freq="6MS"):
            ai = int(np.searchsorted(panel.dates, np.datetime64(a.date(), "D"), side="right") - 1)
            df = run_one(panel, sector, ai, W, F, k, n, keep)
            if df is None:
                continue
            frames.append(df)
            ok = df[df.score >= 0.6]
            print(f"{sector} {a.date()}: {len(df)} cands, {len(ok)} pass, fwd2 up {(ok.f2_ret > 0).mean():.2f} "
                  f"({time.time() - t0:.0f}s)", flush=True)
            pd.concat(frames).to_pickle(HERE / out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--W", type=int, default=2520)
    ap.add_argument("--sectors", default="")
    ap.add_argument("--out", default="trend.pkl")
    a = ap.parse_args()
    main(W=a.W, out=a.out, sectors=[s for s in a.sectors.split(",") if s] or None)
