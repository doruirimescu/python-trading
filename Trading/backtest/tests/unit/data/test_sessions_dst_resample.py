import pandas as pd
import pytest

from tradelab.config import DataCfg
from tradelab.data import get_instrument, load_panel, resample_bars, tag_sessions
from tradelab.data.sources import get_source

ET = "America/New_York"


def rth_1m(start, end, **opts):
    return get_source("synthetic").load("MNQ", start, end, "1m", **opts)


@pytest.mark.parametrize("day,open_utc,close_utc", [
    ("2024-03-08", "14:31", "21:00"),     # Friday before US DST start (EST, UTC-5)
    ("2024-03-11", "13:31", "20:00"),     # Monday after (EDT, UTC-4)
    ("2024-11-01", "13:31", "20:00"),     # Friday before DST end (EDT)
    ("2024-11-04", "14:31", "21:00"),     # Monday after (EST)
])
def test_rth_utc_times_across_dst(day, open_utc, close_utc):
    df = rth_1m(day, day)
    assert len(df) == 390
    assert df.index[0].strftime("%H:%M") == open_utc and df.index[-1].strftime("%H:%M") == close_utc
    loc = df.index.tz_convert(ET)
    assert loc[0].strftime("%H:%M") == "09:31" and loc[-1].strftime("%H:%M") == "16:00"


def test_session_tagging_rth_eth_boundaries_and_globex_dates():
    df = get_source("synthetic").load("MNQ", "2024-03-07", "2024-03-12", "1m", session="globex")
    spec = get_instrument("MNQ")
    t = tag_sessions(df, spec, "1m")
    loc = t.index.tz_convert(ET)
    hm = loc.strftime("%H:%M")
    # end stamps: 09:30 covers 09:29-09:30 (ETH); 09:31 first RTH; 16:00 last RTH; 16:01 ETH
    assert t.loc[hm == "09:30", "session_type"].eq("ETH").all()
    assert t.loc[hm == "09:31", "session_type"].eq("RTH").all()
    assert t.loc[hm == "16:00", "session_type"].eq("RTH").all()
    assert t.loc[hm == "16:01", "session_type"].eq("ETH").all()
    # bars after 18:00 ET belong to the next session_date, before to the same date
    after = t[(loc.hour >= 18)]
    assert (after["session_date"].dt.normalize() > pd.DatetimeIndex(loc[(loc.hour >= 18)].tz_localize(None).normalize())).all()
    before = t[(loc.hour < 17)]
    assert (before["session_date"] == pd.DatetimeIndex(loc[(loc.hour < 17)].tz_localize(None).normalize())).all()
    # 1380 minutes per Globex day (18:00-17:00); Mon Mar 11 is the DST day for date counting only
    full = t.groupby("session_date").size()
    assert (full.iloc[1:-1] == 1380).all()
    assert t.groupby("session_date")["is_session_last"].sum().eq(1).all()
    assert (t.groupby("session_date")["bar_in_session"].first() == 0).all()


def test_sunday_evening_belongs_to_monday_session_across_spring_forward():
    # Sunday 2024-03-10 18:00 ET is the first bar after the DST switch (02:00 that morning)
    df = get_source("synthetic").load("MNQ", "2024-03-08", "2024-03-12", "1m", session="globex")
    t = tag_sessions(df, get_instrument("MNQ"), "1m")
    sun = t[t.index.tz_convert(ET).strftime("%Y-%m-%d %H:%M") == "2024-03-10 18:01"]
    assert len(sun) == 1 and sun["session_date"].iloc[0] == pd.Timestamp("2024-03-11")
    assert sun.index[0].strftime("%H:%M") == "22:01"        # EDT = UTC-4


def test_resample_5m_session_anchored_and_aggregation():
    df = rth_1m("2024-03-11", "2024-03-12", bid_ask=True)
    spec = get_instrument("MNQ")
    r = resample_bars(df, spec, "1m", "5m")
    assert len(r) == 2 * 78
    first = r.iloc[0]
    assert r.index[0].tz_convert(ET).strftime("%H:%M") == "09:35"
    chunk = df.iloc[:5]
    assert first.open == chunk.open.iloc[0] and first.close == chunk.close.iloc[-1]
    assert first.high == chunk.high.max() and first.low == chunk.low.min()
    assert first.volume == chunk.volume.sum() and first.ask_vol == chunk.ask_vol.sum()
    assert not r.partial.any() and r.index[77].tz_convert(ET).strftime("%H:%M") == "16:00"
    # session anchored: each session starts a fresh bin
    assert r.groupby("session_date").size().eq(78).all()


def test_resample_hourly_partial_last_bin_and_no_lookahead_stamp():
    df = rth_1m("2024-03-11", "2024-03-11")
    r = resample_bars(df, get_instrument("MNQ"), "1m", "1h")
    stamps = r.index.tz_convert(ET).strftime("%H:%M").tolist()
    assert stamps == ["10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:00"]
    assert r.partial.tolist() == [False] * 6 + [True]
    assert r.index[-1] == df.index[-1]                       # never stamped after the data
    # the 10:30 bar uses only bars ending <= 10:30
    assert r.close.iloc[0] == df[df.index.tz_convert(ET).strftime("%H:%M") == "10:30"].close.iloc[0]


def test_panel_5m_dst_week_has_consistent_sessions():
    p = load_panel(DataCfg(source="synthetic", symbols=["MNQ"], start="2024-03-04", end="2024-03-15", freq="5m", base_freq="1m"))
    b = p["MNQ"]
    assert b.groupby("session_date").size().eq(78).all()
    loc = b.index.tz_convert(ET)
    assert loc[b["bar_in_session"].to_numpy() == 0].strftime("%H:%M").unique().tolist() == ["09:35"]
    assert p.quality["MNQ"].ok
