"""Does a policy beat plain DCA? One saver is one sample of luck, so every policy is judged over **every start
month**: an account opened then, run for H years, against the plain-DCA account opened the same day.

``edge`` = final wealth / plain DCA's final wealth - 1. A policy "reliably beats DCA" when the edge is positive
for nearly every start month, in every era, and its worst case is small.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from perfectshape.dca.account import AccountConfig, pay_days, simulate


@dataclass
class Windows:
    starts: np.ndarray
    ends: np.ndarray
    years: int


def windows(dates: np.ndarray, years: int, first: str | None = None, last: str | None = None, step: int = 1) -> Windows:
    """Accounts opened on every ``step``-th payment day from ``first``, each valued the day before its
    (12 x years)-th next payment, all inside the data (and closed by ``last``)."""
    pd_idx = np.flatnonzero(pay_days(dates))
    n = 12 * years
    lo = np.datetime64(first, "D") if first else dates[0]
    hi = np.datetime64(last, "D") if last else dates[-1]
    s, e = [], []
    for i in range(0, len(pd_idx) - n, step):
        a, b = pd_idx[i], pd_idx[i + n] - 1
        if dates[a] >= lo and dates[b] <= hi:
            s.append(a)
            e.append(b)
    return Windows(np.array(s, dtype=int), np.array(e, dtype=int), years)


def run(market, target: np.ndarray, w: Windows, cfg: AccountConfig = AccountConfig()) -> dict:
    dates = market.index.values.astype("datetime64[D]")
    return simulate(market["tr"].to_numpy(), dates, target, market["y10"].to_numpy(), market["y3m"].to_numpy(), cfg,
                    starts=w.starts, ends=w.ends)


def edge_stats(res: dict, base: dict) -> dict:
    """Summary of a policy's edge over the benchmark across start months."""
    edge = res["wealth"] / base["wealth"] - 1.0
    dollars = res["wealth"] - base["wealth"]
    n_days = np.maximum(res["debt_days"] + res["cash_days"], 1)
    return {"n": int(len(edge)), "win": float((edge > 0).mean()), "mean": float(edge.mean()), "median": float(np.median(edge)),
            "p10": float(np.quantile(edge, 0.10)), "worst": float(edge.min()), "best": float(edge.max()),
            "usd_median": float(np.median(dollars)), "usd_worst": float(dollars.min()),
            "interest": float(res["interest"].mean()), "calls": int(res["margin_calls"].sum()),
            "debt_share": float((res["debt_days"] / np.maximum(n_days, 1)).mean())}


def compare(market, targets: dict[str, np.ndarray], years: int, cfg: AccountConfig = AccountConfig(),
            first: str | None = None, last: str | None = None, bench: str = "dca") -> dict[str, dict]:
    """``edge_stats`` of every policy in ``targets`` against ``targets[bench]`` over all start months."""
    dates = market.index.values.astype("datetime64[D]")
    w = windows(dates, years, first, last)
    if len(w.starts) == 0:
        return {}
    res = {k: run(market, t, w, cfg) for k, t in targets.items()}
    out = {k: edge_stats(r, res[bench]) for k, r in res.items() if k != bench}
    for k in out:
        out[k]["edges"] = res[k]["wealth"] / res[bench]["wealth"] - 1.0
        out[k]["start_dates"] = dates[w.starts]
    return out
