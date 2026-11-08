"""Regression tests for the correctness review (data layer)."""
import io

import numpy as np
import pandas as pd
import pytest

from tradelab.data import get_instrument, resample_bars, tag_sessions
from tradelab.data.continuous import stitch_continuous
from tradelab.data.sessions import filter_rth
from tradelab.data.sources.files import normalise_table
from tradelab.features.volume_profile import prior_session_levels

ET = "America/New_York"


# ---- 1. daily UTC-midnight bars must keep their own date
def test_daily_utc_midnight_stamps_do_not_shift_to_previous_day():
    raw = pd.DataFrame({"ts_event": pd.to_datetime(["2024-03-04", "2024-03-05"], utc=True),
                        "open": 1., "high": 2., "low": .5, "close": 1.5, "volume": 1.})
    df = normalise_table(raw, "1d", {"ts_col": "ts_event", "tz": "UTC", "stamp": "start"}, {})
    loc = df.index.tz_convert(ET)
    assert [t.strftime("%Y-%m-%d %H:%M") for t in loc] == ["2024-03-04 16:00", "2024-03-05 16:00"]


def test_daily_naive_and_local_tz_stamps():
    raw = pd.DataFrame({"date": ["2024-03-04", "2024-03-05"], "open": 1., "high": 2., "low": .5, "close": 1.5, "volume": 1.})
    df = normalise_table(raw, "1d", {"ts_col": "date", "tz": ET, "stamp": "start"}, {})
    assert [t.strftime("%Y-%m-%d") for t in df.index.tz_convert(ET)] == ["2024-03-04", "2024-03-05"]
    raw2 = raw.assign(date=pd.to_datetime(raw["date"]).dt.tz_localize("Asia/Tokyo"))
    df2 = normalise_table(raw2, "1d", {"ts_col": "date", "tz": "Asia/Tokyo", "stamp": "start"}, {})
    assert [t.strftime("%Y-%m-%d") for t in df2.index.tz_convert(ET)] == ["2024-03-04", "2024-03-05"]


# ---- 2. non-ns datetime resolution (pandas 3 default is us)
def test_microsecond_index_is_normalised_and_resamples_correctly():
    ts = pd.date_range("2024-03-04 09:30", periods=120, freq="1min")
    raw = pd.DataFrame({"ts": ts.strftime("%Y-%m-%d %H:%M:%S"), "open": 1., "high": 2., "low": .5, "close": 1.5, "volume": 1.})
    raw = pd.read_csv(io.StringIO(raw.to_csv(index=False)))
    df = normalise_table(raw, "1m", {"ts_col": "ts", "tz": ET, "stamp": "start"}, {})
    assert str(df.index.dtype).startswith("datetime64[ns")
    spec = get_instrument("MNQ")
    r = resample_bars(tag_sessions(df, spec, "1m"), spec, "1m", "5m")
    assert r.index.is_unique and r.index.is_monotonic_increasing
    assert r.index[0] == pd.Timestamp("2024-03-04 09:35", tz=ET).tz_convert("UTC")
    # also when the caller hands us a us-resolution index directly
    d = tag_sessions(df, spec, "1m")
    d.index = d.index.as_unit("us")
    r2 = resample_bars(d, spec, "1m", "5m")
    assert r2.index.equals(r.index)


# ---- 7. bins straddling the RTH open
def _globex_1m():
    e = pd.date_range("2024-03-04 18:01", "2024-03-05 17:00", freq="1min", tz=ET).tz_convert("UTC").as_unit("ns")
    rng = np.random.default_rng(0)
    c = 100 + np.cumsum(rng.normal(0, .1, len(e)))
    df = pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": c + .1, "low": c - .1, "close": c, "volume": 10.}, index=e)
    return tag_sessions(df, get_instrument("MNQ"), "1m")


@pytest.mark.parametrize("dst", ["1h", "90m"])
def test_eth_fragment_before_rth_open_is_not_stamped_as_rth(dst):
    spec = get_instrument("MNQ")
    df = _globex_1m()
    r = resample_bars(df, spec, "1m", dst)
    ends = r.index.tz_convert(ET)
    # no bar may be stamped later than the data it contains, nor straddle 09:30
    for ts, row in r.iterrows():
        src = df[df.index <= ts]
        assert abs(src.iloc[-1].close - row.close) < 1e-12, ts
    assert r.index[r.index.tz_convert(ET).strftime("%H:%M") == "09:30"].size == 1
    rth = filter_rth(r)
    first_rth_vol = rth.iloc[0]["volume"]
    # the first RTH bar contains only post-09:30 minutes: volume = 10 per minute, <= dst minutes
    assert first_rth_vol <= 10.0 * pd.Timedelta(dst).total_seconds() / 60
    assert rth.index[0].tz_convert(ET).strftime("%H:%M") != "10:00" or dst != "1h"
    assert (ends[r["session_type"].to_numpy() == "ETH"].strftime("%H:%M") != "10:00").all()


# ---- 8. prior_session_levels during the overnight part of a Globex session
def _globex_5m(days=6):
    spec = get_instrument("MNQ")
    rng = np.random.default_rng(3)
    idx = [pd.date_range(d + pd.Timedelta(hours=18, minutes=5), d + pd.Timedelta(days=1, hours=17), freq="5min")
           for d in pd.bdate_range("2024-03-04", periods=days)]
    e = pd.DatetimeIndex(np.concatenate([i.values for i in idx])).tz_localize(ET).tz_convert("UTC").as_unit("ns")
    n = len(e)
    c = np.round((17000 + np.cumsum(rng.normal(0, 2, n))) * 4) / 4
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) + .5, "low": np.minimum(o, c) - .5, "close": c,
                       "volume": rng.integers(10, 500, n).astype(float)}, index=e)
    return tag_sessions(df, spec, "5m")


def test_prior_session_levels_defined_overnight_and_prefix_invariant():
    df = _globex_5m()
    full = prior_session_levels(df, .25)
    # second and later sessions have a prior RTH profile on EVERY bar (including the overnight part)
    later = df["session_date"] > df["session_date"].iloc[0] + pd.Timedelta(days=1)
    assert full.loc[later.to_numpy(), "prior_poc"].notna().all()
    for T in (400, 777, 1100, 1500):
        pre = prior_session_levels(df.iloc[:T], .25)
        a, b = pre.to_numpy(float), full.to_numpy(float)[:T]
        assert np.allclose(a, b, equal_nan=True), T


# ---- scheduled is_session_last (not derived from the data present)
def test_is_session_last_follows_scheduled_close_not_data():
    df = _globex_5m(2)
    cut = df.iloc[:200]                                  # truncated mid-session
    t = tag_sessions(cut, get_instrument("MNQ"), "5m")
    assert not t["is_session_last"].any()
    full = tag_sessions(df, get_instrument("MNQ"), "5m")
    ends = full.index[full["is_session_last"]].tz_convert(ET).strftime("%H:%M")
    assert set(ends) == {"17:00"}
    # RTH-only filtering: scheduled 16:00 close
    rth = filter_rth(full, get_instrument("MNQ"))
    assert set(rth.index[rth["is_session_last"]].tz_convert(ET).strftime("%H:%M")) == {"16:00"}
    t2 = filter_rth(full.iloc[:200], get_instrument("MNQ"))
    assert not t2["is_session_last"].any()


# ---- continuous adjust options
def _two_contracts():
    days = pd.bdate_range("2024-01-02", periods=10)
    rows = []
    for name, off in (("A", 0.0), ("B", 10.0)):
        for k in range(10):
            vol = 1000 if (name == "A" and k < 5) or (name == "B" and k >= 5) else 100
            px = (100 + k) * (1.1 if name == "B" else 1.0)
            rows.append({"ts": days[k] + pd.Timedelta(hours=21), "open": px, "high": px + 1, "low": px - 1, "close": px,
                         "volume": vol, "contract": name})
    df = pd.DataFrame(rows).set_index("ts")
    df.index = df.index.tz_localize("UTC")
    df["session_date"] = df.index.tz_convert(ET).normalize().tz_localize(None)
    return df.sort_index(), days


def test_continuous_adjust_ratio_and_none():
    df, days = _two_contracts()
    d = stitch_continuous(df, method="volume", adjust="difference")
    r = stitch_continuous(df, method="volume", adjust="ratio")
    n = stitch_continuous(df, method="volume", adjust="none")
    sd = r["session_date"]
    k = int(np.flatnonzero((sd == days[6]).to_numpy())[0])
    # ratio: roll gap day5: B/A = 1.1 -> earlier prices scaled by 1.1; return across the roll equals B's own return
    c = r["close"].to_numpy()
    assert c[k] / c[k - 1] == pytest.approx(1.1 * 106 / (1.1 * 105))
    assert np.allclose(r.loc[sd >= days[6], "close"], r.loc[sd >= days[6], "raw_close"])
    assert r["roll_adj"].iloc[0] == pytest.approx(1.1)
    # none: raw prices, no adjustment
    assert np.allclose(n["close"], n["raw_close"]) and np.allclose(n["roll_adj"], 0.0)
    assert not np.allclose(d["close"], n["close"])
    with pytest.raises(ValueError):
        stitch_continuous(df, adjust="bogus")
