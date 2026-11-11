"""Range robustness study: which in-sample features predict that a scan-window band keeps working after the scan.

For every sector SPDR and many past scan ends (as-of dates), enumerate every k vs k ratio of the sector's top
holdings over one window (the scan's own search), keep the best range candidates, then compute
  * in-sample features (only data up to the scan end), and
  * forward outcomes over the next F bars, trading the fixed scan-window band like the Trade Lab final test
    (enter beyond an edge, exit at the median, next-close fills, 5 bps per side per leg, start flat).
Output: one parquet/pickle row per candidate.
"""
from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from perfectshape.config import DataConfig, RatioConfig, ScoringConfig  # noqa: E402
from perfectshape.data.panel import Panel, align  # noqa: E402
from perfectshape.data.sources import load_yfinance  # noqa: E402
from perfectshape.holdings import SECTOR_ETFS, holdings  # noqa: E402
from perfectshape.ratio import search_ratio_window  # noqa: E402
from perfectshape.shapes import get_shape, range_band  # noqa: E402

HERE = Path(__file__).parent
SCORING = ScoringConfig(threshold=0.6, min_annual_return=0.05, min_range_height=0.10, max_range_drift=0.5,
                        complexity_penalty=0.0, range_band_pct=10, range_exit="mid", range_harvest_scale=0.15,
                        range_pain_scale=2.0, range_segments=4, range_speed_days=0)
RANGE = get_shape("range")
PPY = 252


def load_all() -> Panel:
    tick = ["SPY"] + list(SECTOR_ETFS)
    for e in SECTOR_ETFS:
        tick += [h.ticker for h in holdings(e, today=date(2026, 11, 11))[:30]]
    tick = list(dict.fromkeys(tick))
    cfg = DataConfig(source="yfinance", years=22, cache_dir=str(HERE / "cache"), max_age_days=3650)
    series = load_yfinance(tick, cfg, today=date(2026, 11, 11))
    return align(series, max_gap_bars=3)


# ---------------------------------------------------------------- forward / walk-forward band simulation
def simulate(Y, N, D, lo, mid, hi, bps=5.0, exit_frac=0.5):
    """Trade Lab band rules on columns: Y (T, m) log ratio, N, D (T, m) basket values, band per column.
    Decisions on close t, fills on close t+1, start flat at row 0, no entry filled on the last row, open trade
    closed at the last row. Returns dict of arrays (m,)."""
    T, m = Y.shape
    c = bps / 1e4
    side = np.zeros(m)                 # current position
    pend = np.zeros(m, dtype=int)      # 0 none, 1 open long, -1 open short, 2 close, 3 reverse->long, -3 reverse->short
    n0 = np.ones(m); d0 = np.ones(m); e_before = np.ones(m); E = np.ones(m)
    cash = np.ones(m)
    n_closed = np.zeros(m, dtype=int)
    n_open = np.zeros(m, dtype=int)
    wins = np.zeros(m, dtype=int)
    worst = np.zeros(m)                # worst move against an open trade beyond its entry edge, in half-bands
    half = np.maximum((hi - lo) / 2, 1e-12)
    w = hi - lo
    eq = np.ones((T, m))
    t_in = np.zeros(m, dtype=int)
    days = np.zeros(m)

    def value(t):
        nn, dd = N[t] / n0, D[t] / d0
        return np.where(side != 0, E * (1 + side * (nn - dd)), cash)

    def do_close(t, mask, completed):
        nonlocal cash
        v = value(t)
        gross = E * (N[t] / n0 + D[t] / d0)
        newcash = v - c * gross
        cash = np.where(mask, newcash, cash)
        win = mask & (newcash > e_before)
        wins[:] += win.astype(int)
        n_closed[:] += (mask & completed).astype(int)
        days[:] += np.where(mask & completed, t - t_in, 0)
        side[mask] = 0

    def do_open(t, mask, s):
        nonlocal E
        e_before[mask] = cash[mask]
        E = np.where(mask, cash * (1 - c * 2), E)
        n0[mask] = N[t][mask]; d0[mask] = D[t][mask]
        side[mask] = s[mask] if np.ndim(s) else s
        t_in[mask] = t
        n_open[:] += mask.astype(int)

    for t in range(T):
        if t > 0:
            last = t == T - 1
            cl = (pend == 2) | (np.abs(pend) == 3)
            if cl.any():
                do_close(t, cl, np.ones(m, dtype=bool))
            if not last:
                op = (pend == 1) | (pend == -1) | (np.abs(pend) == 3)
                if op.any():
                    do_open(t, op, np.sign(pend).astype(float))
            pend[:] = 0
        y = Y[t]
        against = np.where(side > 0, lo - y, np.where(side < 0, y - hi, 0.0)) / half
        worst = np.maximum(worst, against)
        eq[t] = value(t)
        if t == T - 1:
            break
        sig = np.where(y <= lo, 1, np.where(y >= hi, -1, 0))
        flat = side == 0
        ex = ((side > 0) & (y >= lo + exit_frac * w)) | ((side < 0) & (y <= hi - exit_frac * w))
        rev = ex & (sig != 0) & (sig != side)
        pend = np.where(flat & (sig != 0), sig, pend)
        pend = np.where(ex & ~rev, 2, pend)
        pend = np.where(rev, 3 * sig, pend)
    openm = side != 0
    open_ret = np.where(openm, value(T - 1) / e_before - 1, 0.0)
    if openm.any():
        do_close(T - 1, openm, np.zeros(m, dtype=bool))
    eq[T - 1] = cash
    peak = np.maximum.accumulate(eq, axis=0)
    mdd = ((eq - peak) / peak).min(axis=0)
    return {"n_closed": n_closed, "n_trades": n_open, "wins": wins, "ret": cash - 1.0, "worst": worst,
            "open_ret": open_ret, "was_open": openm.astype(int), "mdd": mdd,
            "days": np.where(n_closed > 0, days / np.maximum(n_closed, 1), np.nan)}


# ---------------------------------------------------------------- features
def ar1(Y):
    """AR(1) on demeaned levels: dy_t = a + b * y_{t-1}. Returns half-life (bars) and t-stat of b (ADF-like)."""
    y0, dy = Y[:-1], np.diff(Y, axis=0)
    y0c = y0 - y0.mean(0)
    dyc = dy - dy.mean(0)
    sxx = (y0c * y0c).sum(0)
    b = (y0c * dyc).sum(0) / np.maximum(sxx, 1e-18)
    res = dyc - b * y0c
    s2 = (res * res).sum(0) / max(len(dy) - 2, 1)
    tstat = b / np.sqrt(s2 / np.maximum(sxx, 1e-18))
    hl = np.where(b < 0, -np.log(2) / np.log1p(np.maximum(b, -0.999)), 1e6)
    return hl, tstat


def variance_ratio(Y, h):
    d1 = np.diff(Y, axis=0)
    dh = Y[h:] - Y[:-h]
    return dh.var(0) / np.maximum(h * d1.var(0), 1e-18)


def crossings(Y, mid):
    above = Y >= mid
    return (above[1:] != above[:-1]).sum(0)


def features(Y, N, D, spy, etf, cfg=SCORING):
    """In-sample features of columns Y (W, m) (log ratio), N, D (W, m), spy/etf (W,) closes."""
    W, m = Y.shape
    q = cfg.range_band_pct
    res = RANGE.score_y(Y, cfg, full=True)
    f = {"score": res.score}
    for k_, v in res.metrics.items():
        f[k_] = v
    lo, mid, hi = range_band(Y, q)
    half = (hi - lo) / 2
    f["half_band"] = half
    hl, t = ar1(Y)
    f["half_life"] = hl
    f["adf_t"] = t
    for h in (20, 60, 120, 250):
        f[f"vr{h}"] = variance_ratio(Y, h)
    dy = np.diff(Y, axis=0)
    vol = dy.std(0) * np.sqrt(PPY)
    f["vol"] = vol
    f["band_over_vol"] = half / np.maximum(vol, 1e-12)          # half-band in years of vol (sqrt time)
    f["cross_per_yr"] = crossings(Y, mid) / (W / PPY)
    # sub-period stability: 5 blocks
    nb = 5
    bounds = np.linspace(0, W, nb + 1).astype(int)
    meds = np.stack([np.median(Y[a:b], axis=0) for a, b in zip(bounds[:-1], bounds[1:])])     # (nb, m)
    f["med_shift_max"] = np.abs(meds - mid).max(0) / np.maximum(half, 1e-12)
    f["med_shift_last"] = np.abs(meds[-1] - mid) / np.maximum(half, 1e-12)
    vols = np.stack([np.diff(Y[a:b], axis=0).std(0) for a, b in zip(bounds[:-1], bounds[1:])])
    f["vol_block_ratio"] = vols.max(0) / np.maximum(vols.min(0), 1e-12)
    f["vol_last_ratio"] = vols[-1] / np.maximum(np.median(vols, 0), 1e-12)
    # per block completed reversions with the full band (repeat, stricter)
    blk_n = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        r = simulate(Y[a:b], N[a:b], D[a:b], lo, mid, hi)
        blk_n.append(r["n_closed"])
    blk_n = np.stack(blk_n)
    f["blk_min_rev"] = blk_n.min(0)
    f["blk_last_rev"] = blk_n[-1]
    f["blk_zero"] = (blk_n == 0).sum(0)
    # the full window, Trade Lab style (in-sample)
    r = simulate(Y, N, D, lo, mid, hi)
    f["is_rev"] = r["n_closed"]
    f["is_ret"] = r["ret"]
    f["is_worst"] = r["worst"]
    f["is_mdd"] = r["mdd"]
    f["is_winrate"] = r["wins"] / np.maximum(r["n_trades"], 1)
    # recent year
    R = 252
    yr = Y[-R:]
    tau = np.arange(R) / PPY
    tc = tau - tau.mean()
    f["recent_slope"] = np.abs((tc @ (yr - yr.mean(0))) / (tc @ tc)) / np.maximum(half, 1e-12)   # half-bands per year
    f["recent_cross"] = crossings(yr, mid)
    f["band_pos"] = (Y[-1] - lo) / np.maximum(hi - lo, 1e-12)
    f["end_dist"] = np.maximum(np.maximum(lo - Y[-1], Y[-1] - hi), 0) / np.maximum(half, 1e-12)
    # walk-forward inside the window: band fitted on Y[:c], traded on the next 2y (or 1y)
    for name, H in (("wf2", 504), ("wf1", 252)):
        ns, rets = [], []
        for frac in (0.4, 0.5, 0.6, 0.7, 0.8) if H == 504 else (0.5, 0.6, 0.7, 0.8, 0.9):
            cut = int(W * frac)
            if cut + H > W:
                continue
            l2, m2, h2 = range_band(Y[:cut], q)
            rr = simulate(Y[cut - 1:cut + H], N[cut - 1:cut + H], D[cut - 1:cut + H], l2, m2, h2)
            ns.append(rr["n_closed"])
            rets.append(rr["ret"])
        ns, rets = np.stack(ns), np.stack(rets)
        f[f"{name}_min_rev"] = ns.min(0)
        f[f"{name}_mean_rev"] = ns.mean(0)
        f[f"{name}_frac2"] = (ns >= 2).mean(0)
        f[f"{name}_min_ret"] = rets.min(0)
        f[f"{name}_mean_ret"] = rets.mean(0)
        f[f"{name}_pos"] = (rets > 0).mean(0)
    # half-vs-half band stability
    a1, m1, b1 = range_band(Y[: W // 2], q)
    a2, m2, b2 = range_band(Y[W // 2:], q)
    f["half_mid_shift"] = np.abs(m2 - m1) / np.maximum(half, 1e-12)
    f["half_height_ratio"] = np.maximum(b2 - a2, b1 - a1) / np.maximum(np.minimum(b2 - a2, b1 - a1), 1e-12)
    # leg co-movement and market exposure
    rn, rd = np.diff(np.log(N), axis=0), np.diff(np.log(D), axis=0)
    rnc, rdc = rn - rn.mean(0), rd - rd.mean(0)
    f["leg_corr"] = (rnc * rdc).sum(0) / np.sqrt((rnc ** 2).sum(0) * (rdc ** 2).sum(0))
    f["leg_vol_ratio"] = np.maximum(rn.std(0), rd.std(0)) / np.maximum(np.minimum(rn.std(0), rd.std(0)), 1e-12)
    for nm, idx in (("spy", spy), ("etf", etf)):
        rs = np.diff(np.log(idx))
        rsc = rs - rs.mean()
        dyc = dy - dy.mean(0)
        f[f"beta_{nm}"] = (rsc @ dyc) / (rsc @ rsc)
        f[f"corr_{nm}"] = (rsc @ dyc) / np.sqrt((rsc @ rsc) * (dyc ** 2).sum(0))
        # rolling 1y beta range: how much the market exposure moves
        betas = []
        for a in range(0, W - 252, 126):
            r_s, r_y = rsc[a:a + 252] - rsc[a:a + 252].mean(), dyc[a:a + 252] - dyc[a:a + 252].mean(0)
            betas.append((r_s @ r_y) / (r_s @ r_s))
        betas = np.stack(betas)
        f[f"beta_{nm}_absmax"] = np.abs(betas).max(0)
        f[f"beta_{nm}_last"] = betas[-1]
    # trend of the ratio vs the market's cumulative move (does it track the market?)
    return f


def neighbor_scores(Xw, num, den, n, cfg=SCORING):
    """Leave-one-out (2 vs 3 / 3 vs 2) and swap-one neighbours: share whose range score clears the threshold."""
    m = len(num)
    k = num.shape[1]
    lv = np.log(np.clip(Xw, 1e-12, None))   # not used directly (means are of prices)
    del lv
    loo_scores = np.zeros((m, 2 * k))
    nb_frac = np.zeros(m)
    nb_mean = np.zeros(m)
    for i in range(m):
        nu, de = list(num[i]), list(den[i])
        curves = []
        for j in range(k):
            a = [x for x in nu if x != nu[j]]
            curves.append(np.log(Xw[:, a].mean(1)) - np.log(Xw[:, de].mean(1)))
        for j in range(k):
            b = [x for x in de if x != de[j]]
            curves.append(np.log(Xw[:, nu].mean(1)) - np.log(Xw[:, b].mean(1)))
        Y = np.column_stack(curves)
        loo_scores[i] = RANGE.score_y(Y, cfg, full=False).score
        others = [x for x in range(n) if x not in nu and x not in de]
        sw = []
        for j in range(k):
            for o in others:
                a = list(nu); a[j] = o
                sw.append(np.log(Xw[:, a].mean(1)) - np.log(Xw[:, de].mean(1)))
                b = list(de); b[j] = o
                sw.append(np.log(Xw[:, nu].mean(1)) - np.log(Xw[:, b].mean(1)))
        S = RANGE.score_y(np.column_stack(sw), cfg, full=False).score
        nb_frac[i] = (S >= cfg.threshold).mean()
        nb_mean[i] = S.mean()
    return {"loo_min": loo_scores.min(1), "loo_mean": loo_scores.mean(1),
            "loo_pass": (loo_scores >= cfg.threshold).mean(1), "nb_frac": nb_frac, "nb_mean": nb_mean}


def member_features(Xw, num, den):
    """Member concentration: share of the ratio's daily variance from its most influential member, the most
    volatile member's vol, and the ratio's vol relative to its members' average vol."""
    R = np.diff(np.log(Xw), axis=0)                      # (W-1, n) member log returns
    k = num.shape[1]
    out = {"member_share_max": [], "member_vol_max": [], "ratio_vs_member_vol": []}
    vols = R.std(0) * np.sqrt(PPY)
    for nu, de in zip(num, den):
        idx = np.r_[nu, de]
        sgn = np.r_[np.ones(k), -np.ones(k)] / k
        C = R[:, idx] * sgn                               # signed contributions
        r = C.sum(1)
        vr = r.var()
        share = np.array([np.cov(C[:, j], r)[0, 1] for j in range(2 * k)]) / max(vr, 1e-18)
        out["member_share_max"].append(share.max())
        out["member_vol_max"].append(vols[idx].max())
        out["ratio_vs_member_vol"].append(np.sqrt(vr * PPY) / vols[idx].mean())
    return {k_: np.array(v) for k_, v in out.items()}


def run_one(panel: Panel, sector: str, asof_idx: int, W: int, F: int, k: int, n_stocks: int, keep: int,
            with_neighbors: bool = True):
    start = asof_idx - W + 1
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
    sub = Panel(panel.dates[start:stop], [panel.symbols[c] for c in cols], panel.close[start:stop][:, cols])
    rc = RatioConfig(k=k, keep_per_window=keep)
    found = search_ratio_window(sub, RANGE, W, W, rc, SCORING)
    if not found:
        return None
    idx = {s: i for i, s in enumerate(sub.symbols)}
    num = np.array([[idx[s] for s in b.members] for b in found])
    den = np.array([[idx[s] for s in b.den_members] for b in found])
    X = sub.close / sub.close[0]
    N = X[:, num].mean(2)
    D = X[:, den].mean(2)
    Y = np.log(N) - np.log(D)
    spy = panel.close[start:stop, sym["SPY"]]
    etf = panel.close[start:stop, sym[sector]]
    f = features(Y[:W], N[:W], D[:W], spy[:W], etf[:W])
    if with_neighbors:
        f.update(neighbor_scores(X[:W], num, den, len(cols)))
    f.update(member_features(X[:W], num, den))
    lo, mid, hi = range_band(Y[:W], SCORING.range_band_pct)
    out = {}
    for H, tag in ((F, "f2"), (F // 2, "f1")):
        r = simulate(Y[W - 1:W + H], N[W - 1:W + H], D[W - 1:W + H], lo, mid, hi)
        for kk, v in r.items():
            out[f"{tag}_{kk}"] = v
    # forward breakout: max distance outside the band in half-bands, and the end distance
    half = (hi - lo) / 2
    Yf = Y[W:W + F]
    out["f2_max_out"] = (np.maximum(np.maximum(lo - Yf, Yf - hi), 0).max(0)) / half
    out["f2_end_out"] = np.maximum(np.maximum(lo - Yf[-1], Yf[-1] - hi), 0) / half
    out["f2_cross"] = crossings(Yf, mid)
    df = pd.DataFrame({**f, **out})
    df.insert(0, "rank", np.arange(1, len(found) + 1))
    df.insert(0, "num", [" ".join(b.members) for b in found])
    df.insert(1, "den", [" ".join(b.den_members) for b in found])
    df.insert(0, "asof", str(panel.dates[asof_idx]))
    df.insert(0, "sector", sector)
    df["n_stocks"] = len(cols)
    df["W"] = W
    return df


def main(W=2520, F=504, k=3, n_stocks=20, keep=300, step_months=6, out="study.pkl", neighbors=True,
         sectors=None, first="2015-01-01", last="2024-11-08"):
    panel = load_all()
    dates = panel.dates
    asofs = pd.date_range(first, last, freq=f"{step_months}MS")
    frames = []
    t0 = time.time()
    for sector in sectors or SECTOR_ETFS:
        for a in asofs:
            ai = int(np.searchsorted(dates, np.datetime64(a.date(), "D"), side="right") - 1)
            t1 = time.time()
            df = run_one(panel, sector, ai, W, F, k, n_stocks, keep, with_neighbors=neighbors)
            if df is None:
                print(f"{sector} {a.date()}: skipped", flush=True)
                continue
            frames.append(df)
            ok = df[df.score >= 0.6]
            print(f"{sector} {a.date()}: {len(df)} cands, {len(ok)} pass, n={df.n_stocks.iloc[0]}, "
                  f"succ(top20)={((ok.head(20).f2_n_closed >= 2) & (ok.head(20).f2_ret > 0)).mean():.2f} "
                  f"{time.time() - t1:.1f}s (total {time.time() - t0:.0f}s)", flush=True)
            pd.concat(frames).to_pickle(HERE / out)
    return pd.concat(frames)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--W", type=int, default=2520)
    ap.add_argument("--F", type=int, default=504)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--keep", type=int, default=300)
    ap.add_argument("--step", type=int, default=6)
    ap.add_argument("--out", default="study.pkl")
    ap.add_argument("--no-neighbors", action="store_true")
    ap.add_argument("--sectors", default="")
    ap.add_argument("--first", default="2015-01-01")
    a = ap.parse_args()
    main(a.W, a.F, a.k, a.n, a.keep, a.step, a.out, not a.no_neighbors,
         [s for s in a.sectors.split(",") if s] or None, a.first)
