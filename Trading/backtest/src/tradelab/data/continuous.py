"""Continuous-futures stitching (volume or calendar roll, difference back-adjustment).

Input: a long frame of bars with a ``contract`` column (several contracts overlapping in time).
Output: one continuous frame.  Prices (open/high/low/close) are difference-back-adjusted so the
roll gap is stripped from P&L; ``raw_close`` keeps the unadjusted close and ``roll_adj`` the
cumulative adjustment applied to that bar.  ``contract`` shows the active contract.
Roll decision uses only data up to the previous session (no look-ahead): for session d the active
contract is the one with the highest *previous-session* volume among contracts not older than the
current one (never rolls backwards).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRICE_COLS = ["open", "high", "low", "close"]


def stitch_continuous(
    bars: pd.DataFrame,
    *,
    method: str = "volume",
    adjust: str = "difference",
    roll_dates: dict | None = None,
) -> pd.DataFrame:
    if adjust not in ("difference", "ratio", "none"):
        raise ValueError(f"adjust must be difference|ratio|none, got {adjust!r}")
    if "contract" not in bars.columns or "session_date" not in bars.columns:
        raise ValueError("bars need 'contract' and 'session_date' columns")
    contracts = list(dict.fromkeys(bars.sort_index()["contract"]))  # order of first appearance
    sdates = np.sort(bars["session_date"].unique())
    vol = bars.groupby(["session_date", "contract"])["volume"].sum().unstack("contract").reindex(sdates).fillna(0.0)
    last_d = bars.groupby("contract")["session_date"].max()
    first_d = bars.groupby("contract")["session_date"].min()
    active, cur = [], contracts[0]
    for k, d in enumerate(sdates):
        if method == "volume" and k > 0:
            prev = vol.iloc[k - 1]
            cand = prev.idxmax()
            if cand != cur and contracts.index(cand) > contracts.index(cur) and first_d[cand] <= d:
                cur = cand
        elif method == "calendar":
            # roll when the current contract has no data on d
            if d > last_d[cur]:
                nxt = [c for c in contracts if contracts.index(c) > contracts.index(cur) and first_d[c] <= d]
                if nxt:
                    cur = nxt[0]
        if d > last_d[cur]:  # contract expired before volume roll triggered
            nxt = [c for c in contracts if contracts.index(c) > contracts.index(cur) and last_d[c] >= d]
            if nxt:
                cur = nxt[0]
        active.append(cur)
    active = pd.Series(active, index=sdates)
    if roll_dates:
        for d, c in roll_dates.items():
            active.loc[active.index >= pd.Timestamp(d)] = c
    mask = bars["contract"].to_numpy() == active.reindex(bars["session_date"]).to_numpy()
    cont = bars[mask].sort_index().copy()
    cont["raw_close"] = cont["close"]
    cont["roll_adj"] = 0.0
    if adjust in ("difference", "ratio"):
        ratio = adjust == "ratio"
        # roll events: active[d] != active[d-1]
        chg = [(sdates[k], active.iloc[k - 1], active.iloc[k]) for k in range(1, len(sdates)) if active.iloc[k] != active.iloc[k - 1]]
        adj_series = pd.Series(1.0 if ratio else 0.0, index=cont.index)
        for d, old, new in reversed(chg):
            prev_d = sdates[np.searchsorted(sdates, d) - 1]
            oc = bars[(bars["contract"] == old) & (bars["session_date"] <= prev_d)]
            nc = bars[(bars["contract"] == new) & (bars["session_date"] <= prev_d)]
            gap = 1.0 if ratio else 0.0
            if len(oc) and len(nc):
                # same-timestamp close comparison: last timestamp where both exist
                common = oc.index.intersection(nc.index)
                t = common.max() if len(common) else None
                n_c, o_c = (nc.loc[t, "close"], oc.loc[t, "close"]) if t is not None else (nc["close"].iloc[-1], oc["close"].iloc[-1])
                if ratio:
                    gap = float(n_c / o_c) if o_c else 1.0
                else:
                    gap = float(n_c - o_c)
            before = (cont["session_date"] < d).to_numpy()
            if ratio:
                adj_series.loc[before] *= gap
            else:
                adj_series.loc[before] += gap
        for c in PRICE_COLS:
            cont[c] = cont[c] * adj_series if ratio else cont[c] + adj_series
        cont["roll_adj"] = adj_series
    cont["contract"] = cont["contract"].astype(str)
    return cont
