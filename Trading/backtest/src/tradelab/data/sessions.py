"""Session tagging (DST-safe, bar-end stamps).

Columns added by :func:`tag_sessions`:
  session_date    naive Timestamp: trading day the bar belongs to
                  (equity: exchange-local date of the bar END; globex: bars ending after 18:00 ET belong to the next date)
  session_type    'RTH' if 09:30 < end_local <= 16:00 (bar covers RTH) else 'ETH'   (daily bars: 'RTH')
  bar_in_session  0-based index of the bar within its session_date (over the bars present)
  is_session_last True on the bar whose END is the SCHEDULED session close (Globex 17:00 ET, equity rth_end; every
                  daily bar). It is calendar knowledge, NOT derived from the data present, so truncating the data
                  (prefix runs, causality cuts) never makes a mid-session bar look like the last one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .calendar import ET, hhmm_to_minutes, is_daily
from .instruments import InstrumentSpec

SESSION_COLS = ["session_date", "session_type", "bar_in_session", "is_session_last"]


def end_local_minutes(idx: pd.DatetimeIndex, tz: str = ET) -> np.ndarray:
    loc = idx.tz_convert(tz)
    return (loc.hour * 60 + loc.minute).to_numpy()


GLOBEX_CLOSE_MIN = 17 * 60


def scheduled_close_minute(spec: InstrumentSpec, rth_only: bool = False) -> int:
    """Local end-minute of the last bar of a session: Globex 17:00 (all-session frames), else rth_end."""
    if spec.session == "globex" and not rth_only:
        return GLOBEX_CLOSE_MIN
    return hhmm_to_minutes(spec.rth_end)


def tag_sessions(df: pd.DataFrame, spec: InstrumentSpec, freq: str) -> pd.DataFrame:
    out = df.drop(columns=[c for c in SESSION_COLS if c in df.columns]).copy()
    if len(out) == 0:
        for c, t in zip(SESSION_COLS, ["datetime64[ns]", "object", "int64", "bool"]):
            out[c] = pd.Series(dtype=t)
        return out
    loc = out.index.tz_convert(spec.tz)
    minutes = (loc.hour * 60 + loc.minute).to_numpy()
    if is_daily(freq):
        sdate = pd.DatetimeIndex(loc.tz_localize(None).normalize())
        stype = np.array(["RTH"] * len(out), dtype=object)
    else:
        rs, re_ = hhmm_to_minutes(spec.rth_start), hhmm_to_minutes(spec.rth_end)
        is_rth = (minutes > rs) & (minutes <= re_)
        stype = np.where(is_rth, "RTH", "ETH").astype(object)
        naive = loc.tz_localize(None)
        if spec.session == "globex":
            # bars ending after 18:00 ET belong to next trading date
            shifted = naive + pd.Timedelta(hours=6)
            sdate = pd.DatetimeIndex(shifted.normalize())
            # a bar ending exactly 18:00 covers the maintenance break; treat as same date (no data in practice)
            sdate = sdate.where(minutes != 18 * 60, naive.normalize())
        else:
            # equity: end exactly at 00:00 (rare) belongs to previous day
            sdate = pd.DatetimeIndex((naive - pd.Timedelta(nanoseconds=1)).normalize())
    out["session_date"] = sdate.values
    out["session_type"] = stype
    g = out.groupby("session_date", sort=False)
    out["bar_in_session"] = g.cumcount().astype("int64")
    if is_daily(freq):
        out["is_session_last"] = True
    else:
        out["is_session_last"] = minutes == scheduled_close_minute(spec)
    return out


def filter_rth(df: pd.DataFrame, spec: InstrumentSpec | None = None) -> pd.DataFrame:
    """Keep RTH bars and re-number bar_in_session / is_session_last (scheduled rth_end; data-derived without a spec)."""
    out = df[df["session_type"] == "RTH"].copy()
    g = out.groupby("session_date", sort=False)
    out["bar_in_session"] = g.cumcount().astype("int64")
    if spec is not None and len(out):
        out["is_session_last"] = end_local_minutes(out.index, spec.tz) == scheduled_close_minute(spec, rth_only=True)
    else:
        out["is_session_last"] = (out["bar_in_session"] == (g["session_date"].transform("size") - 1)).to_numpy()
    return out
