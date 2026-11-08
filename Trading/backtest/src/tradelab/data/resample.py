"""Session-anchored resampling of intraday bars (bar-end stamps in, bar-end stamps out).

Bins are anchored at the RTH open (09:30 local) for RTH bars and at the first bar start of
the (session_date, session_type) group otherwise.  Label=right/closed=right: an N-minute bin
covering [a, a+N) is stamped at a+N (clipped to the last bar end of the group).
Bins that contain fewer 1-unit bars than expected (session end / missing data) get partial=True.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .calendar import freq_to_timedelta
from .instruments import InstrumentSpec
from .sessions import tag_sessions

_SUM = ("volume", "bid_vol", "ask_vol")


def resample_bars(df: pd.DataFrame, spec: InstrumentSpec, src_freq: str, dst_freq: str) -> pd.DataFrame:
    src = freq_to_timedelta(src_freq)
    dst = freq_to_timedelta(dst_freq)
    if dst == src:
        return df
    if dst % src != pd.Timedelta(0):
        raise ValueError(f"{dst_freq} is not a multiple of {src_freq}")
    d = df if "session_date" in df.columns else tag_sessions(df, spec, src_freq)
    d = d.copy()
    d.index = d.index.as_unit("ns")        # all integer-epoch arithmetic below assumes nanosecond resolution
    ends = d.index
    starts = ends - src
    loc_start = starts.tz_convert(spec.tz)
    # anchor per (session_date, run of constant session_type): the ETH bars before the RTH open, the RTH bars and
    # the ETH bars after the RTH close are three separate groups, so no bin ever straddles the 09:30 / 16:00
    # boundary (a straddling bin would be stamped inside RTH although part of its data is pre-open).
    sess_code = pd.factorize(d["session_date"].to_numpy())[0]
    is_rth = (d["session_type"] == "RTH").to_numpy()
    prev_sess = np.r_[-1, sess_code[:-1]]
    prev_rth = np.r_[False, is_rth[:-1]]
    run_start = (sess_code != prev_sess) | (is_rth != prev_rth)
    run_in_sess = (pd.Series(run_start.astype(int)).groupby(sess_code).cumsum() - 1).to_numpy()
    d["_key"] = sess_code.astype("int64") * 8 + np.minimum(run_in_sess, 7)
    rth_open_local = (
        pd.DatetimeIndex(d["session_date"]).tz_localize(None)
        + pd.Timedelta(hours=int(spec.rth_start[:2]), minutes=int(spec.rth_start[3:]))
    ).tz_localize(spec.tz, ambiguous="NaT", nonexistent="NaT")
    rth_open = rth_open_local.tz_convert("UTC")
    first_start = pd.Series(starts, index=d.index).groupby(d["_key"].values).transform("min")
    anchor = pd.Series(np.where(d["session_type"].to_numpy() == "RTH", rth_open.values, first_start.values), index=d.index)
    anchor = pd.to_datetime(anchor, utc=True)
    offs = (pd.Series(starts, index=d.index) - anchor)
    bin_no = (offs // dst).astype("int64").to_numpy()
    d["_bin"] = bin_no
    d["_anchor"] = anchor.values
    d["_start"] = starts
    d["_end"] = ends
    g = d.groupby(["_key", "_bin"], sort=True)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    for c in _SUM:
        if c in d.columns:
            agg[c] = "sum"
    out = g.agg(agg)
    out["_n"] = g.size()
    out["_anchor"] = g["_anchor"].first()
    out["_last_end"] = g["_end"].max()
    out["_session_date"] = g["session_date"].first()
    bins = out.index.get_level_values("_bin").astype("int64").to_numpy()
    nominal_end = pd.DatetimeIndex(pd.to_datetime(out["_anchor"], utc=True)).as_unit("ns").asi8 + (bins + 1) * dst.value
    # clip to the last bar end of the group (session end) -> stamps never exceed data
    group_last = d.groupby("_key")["_end"].max()
    gl = pd.DatetimeIndex(group_last.reindex(out.index.get_level_values("_key")).to_numpy()).as_unit("ns").asi8
    stamp = np.minimum(nominal_end, gl)
    out["partial"] = (out["_n"] < dst // src).to_numpy()
    out.index = pd.DatetimeIndex(pd.to_datetime(stamp, utc=True), name=df.index.name).as_unit("ns")
    out = out.sort_index()
    res = out.drop(columns=[c for c in out.columns if c.startswith("_")])
    res = tag_sessions(res, spec, dst_freq)
    return res
