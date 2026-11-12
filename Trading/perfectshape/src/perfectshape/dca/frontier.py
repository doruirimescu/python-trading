"""Score exposure rules on the two things asked of them: how much they beat plain DCA, and how deep they fall.

For every start month an account follows the rule for H years next to a plain-DCA account opened the same day:

* ``edge``  final wealth / plain DCA's - 1;
* ``dd``    the account's deepest fall (time-weighted, payments taken out) minus plain DCA's deepest fall over the
            same years: negative = the rule fell further than the index.
"""

from __future__ import annotations

import numpy as np

from perfectshape.dca.evaluate import windows
from perfectshape.dca.exposure import ExposureConfig, simulate_exposure
from perfectshape.dca.rules import Rule


def score(market, rules: list[Rule], years: int = 10, cfg: ExposureConfig = ExposureConfig(), first: str | None = None,
          last: str | None = None, step: int = 1, feats=None) -> list[dict]:
    """One row per rule (see the module docstring), over accounts opened every ``step`` payment days."""
    from perfectshape.dca.signals import features

    f = features(market) if feats is None else feats
    dates = market.index.values.astype("datetime64[D]")
    w = windows(dates, years, first, last, step)
    if len(w.starts) == 0:
        return []
    args = (market["tr"].to_numpy(), dates)
    rates = (market["y10"].to_numpy(), market["y3m"].to_numpy())
    base = simulate_exposure(*args, np.ones(len(dates)), *rates, cfg, False, w.starts, w.ends)
    rows = []
    for r in rules:
        res = simulate_exposure(*args, r.array(f), *rates, cfg, r.sell, w.starts, w.ends)
        edge = res["wealth"] / base["wealth"] - 1.0
        dd = res["max_dd"] - base["max_dd"]
        rows.append({"rule": r.name, "family": r.family, "sell": r.sell, "n": int(len(edge)),
                     "win": float((edge > 0).mean()), "median": float(np.median(edge)), "mean": float(edge.mean()),
                     "p10": float(np.quantile(edge, 0.10)), "worst": float(edge.min()), "best": float(edge.max()),
                     "dd_median": float(np.median(res["max_dd"])), "dd_worst": float(res["max_dd"].min()),
                     "dd_vs_dca": float(np.median(dd)), "dd_vs_dca_worst": float(dd.min()),
                     "dd_shallower": float((dd > 0.002).mean()), "dca_dd_median": float(np.median(base["max_dd"])),
                     "dca_dd_worst": float(base["max_dd"].min()),
                     "calls": int(res["margin_calls"].sum()), "wiped": int(res["wiped"].sum()),
                     "avg_exposure": float(res["avg_exposure"].mean()), "max_exposure": float(res["max_exposure"].max()),
                     "interest": float(res["interest"].mean()),
                     "turnover": float((res["traded"] / np.maximum(res["wealth"], 1.0)).mean()),
                     "edges": edge, "dds": dd, "start_dates": dates[w.starts]})
    return rows
