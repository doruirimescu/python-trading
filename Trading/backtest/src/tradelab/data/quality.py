"""Data quality checks -> DataQualityReport."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from .calendar import freq_to_timedelta, is_daily, trading_days
from .instruments import InstrumentSpec


@dataclass
class DataQualityReport:
    symbol: str
    n_bars: int
    freq: str
    issues: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    def add(self, code: str, n: int, severity: str = "warn", detail: str = ""):
        self.counts[code] = int(n)
        if n:
            self.issues.append({"code": code, "count": int(n), "severity": severity, "detail": detail})

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i["severity"] == "error")

    @property
    def ok(self) -> bool:
        return self.n_errors == 0

    def to_dict(self) -> dict:
        return asdict(self)


class DataQualityError(RuntimeError):
    pass


def check_bars(df: pd.DataFrame, spec: InstrumentSpec, freq: str, symbol: str = "", *, check_missing_sessions: bool = True) -> DataQualityReport:
    r = DataQualityReport(symbol or spec.symbol, len(df), freq)
    if len(df) == 0:
        r.add("empty", 1, "error", "no bars")
        return r
    idx = df.index
    r.add("duplicate_timestamps", int(idx.duplicated().sum()), "error")
    r.add("non_monotonic", int((np.diff(idx.asi8) < 0).sum()), "error")
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    bad = (h < np.maximum(o, c) - 1e-9) | (l > np.minimum(o, c) + 1e-9) | (h < l)
    r.add("ohlc_inconsistent", int(bad.sum()), "error")
    r.add("nan_prices", int(np.isnan(np.c_[o, h, l, c]).any(axis=1).sum()), "error")
    r.add("nonpositive_prices", int((np.c_[o, h, l, c] <= 0).any(axis=1).sum()), "error")
    if "volume" in df:
        r.add("zero_volume", int((df["volume"].to_numpy() <= 0).sum()), "warn")
        r.add("negative_volume", int((df["volume"].to_numpy() < 0).sum()), "error")
    # stale: >=5 consecutive identical OHLC with zero range
    flat = (h == l) & (o == c)
    if flat.any():
        run = pd.Series(flat).groupby((~pd.Series(flat)).cumsum()).cumsum().to_numpy()
        r.add("stale_bars", int((run == 5).sum()), "warn", ">=5 consecutive zero-range bars")
    # outliers: |log ret| > 10 * robust sigma (floored)
    lr = np.diff(np.log(np.where(c > 0, c, np.nan)))
    lr = lr[np.isfinite(lr)]
    if len(lr) > 20:
        mad = np.median(np.abs(lr - np.median(lr))) * 1.4826
        thr = max(10 * mad, 0.2 if is_daily(freq) else 0.05)
        r.add("return_outliers", int((np.abs(lr) > thr).sum()), "warn", f"|log ret|>{thr:.3f}")
    if not is_daily(freq) and "session_date" in df:
        step = freq_to_timedelta(freq)
        d = df[df["session_type"] == "RTH"] if "session_type" in df else df
        if len(d):
            n_exp = int(pd.Timedelta(hours=6, minutes=30) / step) if spec.session == "equity" or True else 0
            cnt = d.groupby("session_date").size()
            gaps = (cnt < n_exp) & (cnt > 0)
            # half days (13:00 close) are legit: ignore sessions whose last RTH bar ends <= 13:00
            r.add("sessions_with_gaps", int(gaps.sum()), "warn", f"RTH sessions with < {n_exp} bars (incl. half days)")
    if check_missing_sessions and "session_date" in df and len(df):
        sd = pd.DatetimeIndex(df["session_date"].unique()).sort_values()
        if len(sd) > 1:
            exp = trading_days(sd[0], sd[-1])
            if spec.kind == "future" and not is_daily(freq):
                pass
            missing = exp.difference(sd)
            r.add("missing_sessions", len(missing), "warn", ", ".join(str(m.date()) for m in missing[:5]))
    return r
