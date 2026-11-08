"""Offline tests for the Databento pipeline (fake client, synthetic trades)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tradelab.data.orderflow_bars import aggregate_trades, combine_bars
from tradelab.data.sources import get_source
from tradelab.data.sources.databento import (
    BudgetExceeded, DatabentoDownloader, day_windows, merge_chunks, month_chunks)

ROOT = Path(__file__).resolve().parents[3]


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def trades_df(rows):
    """rows: (iso_utc, price, size, side)"""
    return pd.DataFrame({
        "ts_event": pd.to_datetime([r[0] for r in rows], utc=True, format="ISO8601"),
        "price": [r[1] for r in rows], "size": [r[2] for r in rows], "side": [r[3] for r in rows],
        "instrument_id": 42})


class FakeStore:
    def __init__(self, df): self.df = df
    def to_df(self, count=None, **_):
        if count is None:
            return self.df
        return iter([self.df.iloc[i:i + 3] for i in range(0, len(self.df), 3)] or [self.df])


class FakeClient:
    """Deterministic: one trade per weekday-minute inside requested range, 1 trade/min at 14:30-14:35 UTC only."""
    def __init__(self, cost_per_hour=0.01):
        self.calls = []
        self.cost_per_hour = cost_per_hour
        self.metadata = self
        self.timeseries = self
        self.symbology = self

    def get_dataset_range(self, dataset): return {"start": "2010-06-06T00:00:00+00:00", "end": "2026-01-01T00:00:00+00:00"}
    def get_cost(self, **kw):
        self.calls.append(("cost", kw))
        h = (pd.Timestamp(kw["end"]) - pd.Timestamp(kw["start"])).total_seconds() / 3600
        return h * self.cost_per_hour
    def resolve(self, **kw):
        return {"result": {kw["symbols"][0]: [
            {"d0": "2024-01-01", "d1": "2024-01-16", "s": "NQH4"}, {"d0": "2024-01-16", "d1": "2024-03-01", "s": "NQM4"}]}}
    def get_range(self, **kw):
        self.calls.append(("get", kw))
        s, e = pd.Timestamp(kw["start"]), pd.Timestamp(kw["end"])
        idx = pd.date_range(s.ceil("min"), e - pd.Timedelta(minutes=1), freq="1min")
        idx = idx[(idx.hour == 14) & (idx.minute < 5) & (idx.dayofweek < 5)]
        if kw["schema"] == "trades":
            df = pd.DataFrame({"ts_event": idx, "price": 100.0 + np.arange(len(idx)) % 3, "size": 2,
                               "side": ["B", "A", "N"] * (len(idx) // 3 + 1) if False else (["B", "A", "N"] * len(idx))[:len(idx)],
                               "instrument_id": 7})
            return FakeStore(df)
        df = pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10, "instrument_id": 7}, index=idx)
        df.index.name = "ts_event"
        return FakeStore(df)


def test_month_chunks_and_day_windows_dst():
    ch = month_chunks("2024-01-15", "2024-03-10")
    assert [c[0].strftime("%Y-%m-%d") for c in ch] == ["2024-01-15", "2024-02-01", "2024-03-01"]
    assert ch[-1][1] == pd.Timestamp("2024-03-11", tz="UTC")
    w = day_windows(pd.Timestamp("2024-03-08", tz="UTC"), pd.Timestamp("2024-03-13", tz="UTC"), "09:00-11:30")
    starts = [s.strftime("%m-%d %H:%M") for s, _ in w]
    # Fri 3/8 EST (14:00Z), Mon 3/11 EDT (13:00Z) after DST start 3/10, weekend skipped
    assert starts == ["03-08 14:00", "03-11 13:00", "03-12 13:00"]
    assert w[0][1] - w[0][0] == pd.Timedelta(hours=2, minutes=30)


def test_trades_to_bars_hand_computed():
    t = trades_df([
        ("2024-01-02T14:30:00.5Z", 100.0, 3, "B"),   # buy aggressor -> ask_vol
        ("2024-01-02T14:30:10Z", 101.0, 2, "A"),     # sell aggressor -> bid_vol
        ("2024-01-02T14:30:59.9Z", 99.5, 1, "N"),
        ("2024-01-02T14:31:00Z", 100.5, 4, "A"),     # boundary belongs to next bar
        ("2024-01-02T14:36:00Z", 102.0, 5, "B"),
    ])
    r = aggregate_trades(t, freq="1min", footprint_freq="5min")
    b = r.bars
    first = b.loc[pd.Timestamp("2024-01-02T14:31:00Z")]  # bar-END stamp
    assert (first.open, first.high, first.low, first.close) == (100.0, 101.0, 99.5, 99.5)
    assert (first.volume, first.ask_vol, first.bid_vol, first.n_trades) == (6, 3, 2, 3)
    second = b.loc[pd.Timestamp("2024-01-02T14:32:00Z")]
    assert (second.bid_vol, second.ask_vol, second.volume) == (4, 0, 4)
    assert len(b) == 3 and b.index.tz is not None
    fp = r.footprint
    f5 = fp[fp.ts == pd.Timestamp("2024-01-02T14:35:00Z")].set_index("price")
    assert f5.loc[100.0, "ask_vol"] == 3 and f5.loc[101.0, "bid_vol"] == 2 and f5.loc[99.5, ["bid_vol", "ask_vol"]].sum() == 0
    assert f5.loc[100.5, "bid_vol"] == 4
    assert fp.groupby("ts")[["bid_vol", "ask_vol"]].sum().loc[pd.Timestamp("2024-01-02T14:35:00Z")].sum() == 9
    assert fp.ts.nunique() == 2


def test_aggregation_tod_window_and_dst():
    # 08:29 and 08:30 ET in winter (13:29Z/13:30Z) and summer (12:29Z/12:30Z); 12:00 ET excluded
    t = trades_df([
        ("2024-01-02T13:29:30Z", 1, 1, "B"), ("2024-01-02T13:30:30Z", 2, 1, "B"), ("2024-01-02T17:00:00Z", 3, 1, "B"),
        ("2024-07-02T12:29:30Z", 1, 1, "B"), ("2024-07-02T12:30:30Z", 2, 1, "B"), ("2024-07-02T16:00:00Z", 3, 1, "B"),
    ])
    b = aggregate_trades(t, tod_window=("08:30", "12:00")).bars
    assert list(b.index.strftime("%m-%d %H:%M")) == ["01-02 13:31", "07-02 12:31"]
    assert list(b.close) == [2, 2]


def test_combine_bars_batches_equal_single_pass():
    rows = [(f"2024-01-02T14:30:{s:02d}Z", 100 + s % 4, 1 + s % 3, "BAN"[s % 3]) for s in range(0, 50, 2)]
    t = trades_df(rows)
    whole = aggregate_trades(t).bars
    parts = combine_bars([aggregate_trades(t.iloc[:7]).bars, aggregate_trades(t.iloc[7:]).bars])
    pd.testing.assert_frame_equal(whole, parts)


def test_chunking_resume_and_atomic(tmp_path):
    c = FakeClient()
    dl = DatabentoDownloader(c, tmp_path, max_cost_usd=1e6, log=lambda *_: None, now=pd.Timestamp("2025-06-01", tz="UTC"))
    rep = dl.download("NQ.v.0", "ohlcv-1m", "2024-01-01", "2024-02-29")
    assert [r.status for r in rep] == ["downloaded", "downloaded"]
    d = tmp_path / "GLBX.MDP3" / "ohlcv-1m" / "NQ.v.0"
    assert sorted(p.name for p in d.iterdir()) == ["2024-01.parquet", "2024-02.parquet"]  # no .tmp left
    df = pd.read_parquet(d / "2024-01.parquet")
    assert {"instrument_id", "contract"} <= set(df.columns)
    assert set(df.contract) == {"NQH4", "NQM4"}          # roll visible from symbology intervals
    assert df.loc[pd.to_datetime(df.ts_event).dt.day < 16, "contract"].eq("NQH4").all()
    n_get = sum(1 for k, _ in c.calls if k == "get")
    dl2 = DatabentoDownloader(c, tmp_path, max_cost_usd=0.0, log=lambda *_: None, now=pd.Timestamp("2025-06-01", tz="UTC"))
    rep2 = dl2.download("NQ.v.0", "ohlcv-1m", "2024-01-01", "2024-02-29")
    assert [r.status for r in rep2] == ["skipped", "skipped"]
    assert sum(1 for k, _ in c.calls if k == "get") == n_get and dl2.total_cost == 0


def test_partial_month_refetched(tmp_path):
    c = FakeClient()
    now = pd.Timestamp("2024-01-10", tz="UTC")
    dl = DatabentoDownloader(c, tmp_path, max_cost_usd=1e6, log=lambda *_: None, now=now)
    dl.download("NQ.v.0", "ohlcv-1m", "2024-01-01", "2024-01-09")
    d = tmp_path / "GLBX.MDP3" / "ohlcv-1m" / "NQ.v.0"
    assert (d / "2024-01.partial.parquet").exists() and not (d / "2024-01.parquet").exists()
    dl = DatabentoDownloader(c, tmp_path, max_cost_usd=1e6, log=lambda *_: None, now=pd.Timestamp("2024-03-01", tz="UTC"))
    dl.download("NQ.v.0", "ohlcv-1m", "2024-01-01", "2024-01-31")
    assert (d / "2024-01.parquet").exists() and not (d / "2024-01.partial.parquet").exists()


def test_budget_abort_before_exceeding(tmp_path):
    c = FakeClient(cost_per_hour=0.01)           # Jan ~ 744h -> 7.44, Feb 2024 ~ 696h -> 6.96
    logs = []
    dl = DatabentoDownloader(c, tmp_path, max_cost_usd=10.0, log=logs.append, now=pd.Timestamp("2025-06-01", tz="UTC"))
    with pytest.raises(BudgetExceeded):
        dl.download("NQ.v.0", "ohlcv-1m", "2024-01-01", "2024-03-31")
    assert dl.total_cost == pytest.approx(7.44)
    d = tmp_path / "GLBX.MDP3" / "ohlcv-1m" / "NQ.v.0"
    assert [p.name for p in d.iterdir()] == ["2024-01.parquet"]
    assert sum(1 for k, kw in c.calls if k == "get") == 1
    assert any("running" in str(m) for m in logs)


def test_dry_run_downloads_nothing(tmp_path):
    c = FakeClient()
    dl = DatabentoDownloader(c, tmp_path, max_cost_usd=100, log=lambda *_: None)
    dl.download("NQ.v.0", "trades", "2024-01-01", "2024-01-31", dry_run=True)
    assert not any(k == "get" for k, _ in c.calls) and not (tmp_path / "GLBX.MDP3").exists()


def test_daily_window_cuts_requested_range_and_cost(tmp_path):
    c = FakeClient(cost_per_hour=0.01)
    full = DatabentoDownloader(c, tmp_path / "f", log=lambda *_: None).chunk_cost("NQ.v.0", "trades", *month_chunks("2024-03-01", "2024-03-31")[0])
    win = DatabentoDownloader(c, tmp_path / "w", daily_window="09:00-11:30", log=lambda *_: None).chunk_cost(
        "NQ.v.0", "trades", *month_chunks("2024-03-01", "2024-03-31")[0])
    assert win == pytest.approx(21 * 2.5 * 0.01) and win < full / 10


def test_trades_download_footprint_and_merge_through_parquet_preset(tmp_path):
    c = FakeClient()
    dl = DatabentoDownloader(c, tmp_path, max_cost_usd=1e6, daily_window="09:00-11:30", footprint_freq="5min",
                             batch_rows=3, log=lambda *_: None, now=pd.Timestamp("2025-06-01", tz="UTC"))
    dl.download("MNQ.v.0", "trades", "2024-01-02", "2024-01-31")
    fp = pd.read_parquet(dl.footprint_path("MNQ.v.0", pd.Timestamp("2024-01-01", tz="UTC")))
    assert {"ts", "price", "bid_vol", "ask_vol"} == set(fp.columns) and fp.bid_vol.dtype == np.float32
    out = merge_chunks(tmp_path, "MNQ.v.0", "trades", tmp_path / "MNQ_1m.parquet")
    raw = pd.read_parquet(out)
    assert {"ts_event", "bid_vol", "ask_vol", "n_trades", "contract"} <= set(raw.columns)
    src = get_source("parquet")
    df = src.load("MNQ", "2024-01-02", "2024-01-31", "1m", path=str(out), preset="databento_ohlcv_1m")
    assert {"bid_vol", "ask_vol", "volume", "contract"} <= set(df.columns)
    assert df.index.tz is not None
    # bar-end convention: ts_event(open) + 1 min
    assert df.index[0] == pd.Timestamp(raw.ts_event.iloc[0]) + pd.Timedelta("1min")
    assert (df.bid_vol + df.ask_vol <= df.volume).all()


def test_panel_roundtrip_has_bid_ask_vol(tmp_path):
    from tradelab.config.schema import DataCfg
    from tradelab.data.orderflow_bars import write_bars_parquet
    from tradelab.data.panel import load_panel

    rng = np.random.default_rng(0)
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=120, freq="1min") + pd.Timedelta(seconds=5)  # 09:30 ET onward
    t = pd.DataFrame({"ts_event": ts.repeat(3), "price": 100 + rng.integers(0, 8, 360) * 0.25,
                      "size": rng.integers(1, 5, 360), "side": rng.choice(list("ABN"), 360), "instrument_id": 7})
    bars = aggregate_trades(t).bars
    p = tmp_path / "MNQ_1m.parquet"
    write_bars_parquet(bars, p)
    cfg = DataCfg(source="parquet", symbols=["MNQ"], start="2024-01-02", end="2024-01-02", freq="5m", base_freq="1m",
                  session="rth", options={"path": str(p), "preset": "databento_ohlcv_1m"})
    panel = load_panel(cfg, cache_root=tmp_path / "cache")
    b = panel["MNQ"]
    assert {"bid_vol", "ask_vol", "volume"} <= set(b.columns)
    assert b.bid_vol.sum() == pytest.approx(bars.bid_vol.sum()) and b.ask_vol.sum() == pytest.approx(bars.ask_vol.sum())


def test_planner_with_fake_client():
    plan = _load_script("databento_plan")
    rows = plan.plan_rows(FakeClient(), "09:00-11:30", samples=3, end="2024-03-01")
    txt = plan.render(rows)
    assert txt.startswith("| Job") and "2010-06-06" in txt and txt.count("daily 09:00-11:30 ET") == 3
    assert plan.main([], client=FakeClient()) == 0
