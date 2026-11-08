import json

import numpy as np
import pandas as pd
import pytest

from tradelab.config import DataCfg
from tradelab.data import get_instrument, load_panel, tag_sessions
from tradelab.data.continuous import stitch_continuous
from tradelab.data.quality import check_bars
from tradelab.data.sources import CostLimitExceeded, DatabentoSource, get_source, list_sources
from tradelab.data.sources.files import normalise_table
from tradelab.data.sources.yfinance_src import normalise_yf_frame

ET = "America/New_York"


def test_sources_registered():
    assert set(list_sources()) == {"yfinance", "csv", "parquet", "databento", "synthetic"}


def test_synthetic_deterministic_and_seed_sensitive_and_valid():
    s = get_source("synthetic")
    a = s.load("MNQ", "2024-01-02", "2024-01-31", "1m", seed=3, bid_ask=True)
    b = s.load("MNQ", "2024-01-02", "2024-01-31", "1m", seed=3, bid_ask=True)
    c = s.load("MNQ", "2024-01-02", "2024-01-31", "1m", seed=4, bid_ask=True)
    pd.testing.assert_frame_equal(a, b)
    assert not np.allclose(a.close.to_numpy(), c.close.to_numpy())
    assert (a.high >= a[["open", "close"]].max(axis=1)).all() and (a.low <= a[["open", "close"]].min(axis=1)).all()
    assert ((a.close / 0.25) % 1 == 0).all()                          # on tick grid
    assert np.allclose(a.bid_vol + a.ask_vol, a.volume)
    # U-shaped volume: first/last half hour busier than midday
    loc = a.index.tz_convert(ET)
    m = loc.hour * 60 + loc.minute
    mid = a.volume[(m > 12 * 60) & (m <= 13 * 60)].mean()
    assert a.volume[(m > 570) & (m <= 600)].mean() > 1.5 * mid


def test_synthetic_daily_and_holidays_removed():
    d = get_source("synthetic").load("SPY", "2024-01-01", "2024-12-31", "1d")
    days = d.index.tz_convert(ET).normalize().tz_localize(None)
    assert pd.Timestamp("2024-07-04") not in days and pd.Timestamp("2024-11-28") not in days
    assert pd.Timestamp("2024-03-29") not in days                     # Good Friday
    assert len(d) == 252
    assert d.index.tz_convert(ET)[0].strftime("%H:%M") == "16:00"


def test_databento_preset_open_stamp_converted_to_bar_end(tmp_path):
    raw = pd.DataFrame({
        "ts_event": ["2024-01-02T14:30:00Z", "2024-01-02T14:31:00Z", "2024-01-02T14:32:00Z"],
        "open": [10.0, 11, 12], "high": [11.0, 12, 13], "low": [9.0, 10, 11], "close": [10.5, 11.5, 12.5], "volume": [5, 6, 7],
        "symbol": "MNQ.v.0",
    })
    p = tmp_path / "MNQ.csv"
    raw.to_csv(p, index=False)
    df = get_source("csv").load("MNQ", None, None, "1m", path=str(p), preset="databento_ohlcv_1m")
    assert df.index[0] == pd.Timestamp("2024-01-02T14:31:00Z")          # open 14:30 -> end 14:31
    assert df.index.tz is not None and df.close.iloc[0] == 10.5
    loc = df.index.tz_convert(ET)
    assert loc[0].strftime("%H:%M") == "09:31"
    # parquet twin
    pq = tmp_path / "MNQ.parquet"
    raw.assign(ts_event=pd.to_datetime(raw.ts_event)).to_parquet(pq)
    df2 = get_source("parquet").load("MNQ", None, None, "1m", path=str(pq), preset="databento_ohlcv_1m")
    pd.testing.assert_frame_equal(df, df2)


def test_firstrate_preset_et_open_stamps_dst():
    raw = pd.DataFrame({"ts": ["2024-03-11 09:30:00", "2024-03-11 09:31:00"], "open": [1.0, 2], "high": [2.0, 3], "low": [0.5, 1], "close": [1.5, 2.5], "volume": [1, 1]})
    from tradelab.data.sources.files import PRESETS
    df = normalise_table(raw, "1m", PRESETS["firstrate"], {})
    assert df.index[0] == pd.Timestamp("2024-03-11T13:31:00Z")          # EDT: 09:30 open -> 09:31 end = 13:31Z


def test_yfinance_normalisation_daily_and_intraday():
    raw = pd.DataFrame({"Open": [1.0, 2], "High": [2.0, 3], "Low": [0.5, 1], "Close": [1.5, 2.5], "Volume": [10, 20]},
                       index=pd.DatetimeIndex(["2024-03-08", "2024-03-11"]).tz_localize(ET))
    d = normalise_yf_frame(raw, "1d")
    assert d.index[0] == pd.Timestamp("2024-03-08T21:00:00Z") and d.index[1] == pd.Timestamp("2024-03-11T20:00:00Z")
    raw_i = raw.copy()
    raw_i.index = pd.DatetimeIndex(["2024-03-11 09:30", "2024-03-11 09:35"]).tz_localize(ET)
    i = normalise_yf_frame(raw_i, "5m")
    assert i.index[0] == pd.Timestamp("2024-03-11T13:35:00Z")


class FakeHist:
    def __init__(self, cost):
        self.cost = cost
        self.calls = []
        self.metadata = self
        self.timeseries = self

    def get_cost(self, **kw):
        self.calls.append("cost")
        return self.cost

    def get_range(self, **kw):
        self.calls.append("range")
        idx = pd.DatetimeIndex(["2024-01-02T14:30:00Z", "2024-01-02T14:31:00Z"], name="ts_event")
        df = pd.DataFrame({"open": [1.0, 2], "high": [2.0, 3], "low": [0.5, 1], "close": [1.5, 2.5], "volume": [1, 2], "symbol": "MNQ.v.0"}, index=idx)

        class S:
            def to_df(self_inner):
                return df
        return S()


def test_databento_refuses_above_max_cost_and_downloads_below(tmp_path):
    c = FakeHist(cost=12.0)
    src = DatabentoSource(client=c, store_dir=tmp_path)
    with pytest.raises(CostLimitExceeded):
        src.load("MNQ.v.0", "2024-01-02", "2024-01-02", "1m")
    assert c.calls == ["cost"]                                         # never downloaded
    with pytest.raises(CostLimitExceeded):
        src.load("MNQ.v.0", "2024-01-02", "2024-01-02", "1m", max_cost_usd=1.0)
    c2 = FakeHist(cost=0.4)
    src2 = DatabentoSource(client=c2, store_dir=tmp_path)
    df = src2.load("MNQ.v.0", "2024-01-02", "2024-01-02", "1m")
    assert c2.calls == ["cost", "range"] and df.index[0] == pd.Timestamp("2024-01-02T14:31:00Z")
    c3 = FakeHist(cost=99)
    df3 = DatabentoSource(client=c3, store_dir=tmp_path).load("MNQ.v.0", "2024-01-02", "2024-01-02", "1m")   # cached: no API call
    assert c3.calls == [] and len(df3) == 2
    assert src2.estimate_cost("MNQ.v.0", "2024-01-02", "2024-01-02") == 0.4


def test_databento_requires_key(monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DATABENTO_API_KEY"):
        DatabentoSource().client


@pytest.mark.network
def test_yfinance_live_daily():
    d = get_source("yfinance").load("SPY", "2024-01-02", "2024-01-31", "1d")
    assert len(d) > 15


def test_quality_checks_flag_problems():
    spec = get_instrument("SPY")
    df = get_source("synthetic").load("SPY", "2024-01-01", "2024-06-30", "1d")
    df = tag_sessions(df, spec, "1d")
    assert check_bars(df, spec, "1d").ok
    bad = df.copy()
    bad.iloc[5, bad.columns.get_loc("high")] = bad.iloc[5]["low"] - 1          # high < low
    bad.iloc[10, bad.columns.get_loc("volume")] = 0
    bad = pd.concat([bad, bad.iloc[[20]]]).sort_index()                         # duplicate ts
    bad = bad.drop(bad.index[30:33])                                           # missing sessions
    bad = tag_sessions(bad, spec, "1d")
    rep = check_bars(bad, spec, "1d")
    assert not rep.ok
    c = rep.counts
    assert c["ohlc_inconsistent"] >= 1 and c["duplicate_timestamps"] == 1 and c["zero_volume"] == 1 and c["missing_sessions"] >= 3
    json.dumps(rep.to_dict(), default=str)


def test_strict_quality_raises(tmp_path):
    p = tmp_path / "x.csv"
    pd.DataFrame({"date": ["2024-01-02", "2024-01-03"], "open": [1, 1], "high": [0.5, 2], "low": [1, 1], "close": [1, 1], "volume": [1, 1]}).to_csv(p, index=False)
    from tradelab.data.quality import DataQualityError
    with pytest.raises(DataQualityError):
        load_panel(DataCfg(source="csv", symbols=["X"], freq="1d", options={"path": str(p)}, strict_quality=True))


def _contracts():
    """Two overlapping daily contracts; B has higher volume from day 5."""
    days = pd.bdate_range("2024-01-02", periods=10)
    rows = []
    for name, lo, hi, off in (("A", 0, 7, 0.0), ("B", 3, 10, 5.0)):
        for k in range(lo, hi):
            vol = 1000 if (name == "A" and k < 5) or (name == "B" and k >= 5) else 100
            px = 100 + k + off
            rows.append({"ts": days[k] + pd.Timedelta(hours=21), "open": px, "high": px + 1, "low": px - 1, "close": px, "volume": vol, "contract": name})
    df = pd.DataFrame(rows).set_index("ts")
    df.index = df.index.tz_localize("UTC")
    df["session_date"] = df.index.tz_convert(ET).normalize().tz_localize(None)
    return df.sort_index(), days


def test_continuous_volume_roll_difference_adjust():
    df, days = _contracts()
    cont = stitch_continuous(df, method="volume")
    sd = cont["session_date"]
    # volume roll decided from PREVIOUS session volume: B becomes top on day idx5, roll takes effect day idx6
    assert (cont.loc[sd < days[6], "contract"] == "A").all() and (cont.loc[sd >= days[6], "contract"] == "B").all()
    # roll gap = B - A on the last common session before the roll (day 5): (105+5) - 105 = 5
    after = cont[sd >= days[6]]
    before = cont[sd < days[6]]
    assert np.allclose(after["roll_adj"], 0.0) and np.allclose(before["roll_adj"], 5.0)
    # adjusted series is continuous across the roll: the day-over-day change equals B's own change
    c = cont["close"].to_numpy()
    k = int(np.flatnonzero((sd == days[6]).to_numpy())[0])
    assert c[k] - c[k - 1] == pytest.approx(1.0)
    raw = cont["raw_close"].to_numpy()
    assert raw[k] - raw[k - 1] == pytest.approx(6.0)                    # un-adjusted jump present only in raw


def test_continuous_calendar_roll_on_expiry():
    df, days = _contracts()
    cont = stitch_continuous(df, method="calendar")
    sd = cont["session_date"]
    assert (cont.loc[sd <= days[6], "contract"] == "A").all() and (cont.loc[sd > days[6], "contract"] == "B").all()
