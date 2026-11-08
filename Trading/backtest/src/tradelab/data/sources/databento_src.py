"""Databento source (real client). Reads DATABENTO_API_KEY. Always checks cost first."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from ...util.hashing import stable_hash
from ..base import clip_range
from .files import normalise_table

SCHEMAS = {"1m": "ohlcv-1m", "1s": "ohlcv-1s", "1h": "ohlcv-1h", "1d": "ohlcv-1d"}


class CostLimitExceeded(RuntimeError):
    pass


class DatabentoSource:
    name = "databento"

    def __init__(self, client=None, store_dir: str | Path = "data_store/databento"):
        self._client = client
        self.store_dir = Path(store_dir)

    @property
    def client(self):
        if self._client is None:
            key = os.environ.get("DATABENTO_API_KEY")
            if not key:
                raise RuntimeError("DATABENTO_API_KEY is not set")
            import databento as db

            self._client = db.Historical(key)
        return self._client

    def _args(self, symbol, start, end, freq, dataset, stype_in, schema):
        return dict(
            dataset=dataset,
            symbols=[symbol],
            schema=schema or SCHEMAS.get(freq.lower(), "ohlcv-1m"),
            stype_in=stype_in,
            start=pd.Timestamp(start).tz_localize("UTC").isoformat() if start and pd.Timestamp(start).tz is None else start,
            end=(pd.Timestamp(end) + pd.Timedelta(days=1)).tz_localize("UTC").isoformat() if end and pd.Timestamp(end).tz is None else end,
        )

    def estimate_cost(self, symbol, start, end, freq="1m", *, dataset="GLBX.MDP3", stype_in="continuous", schema=None) -> float:
        a = self._args(symbol, start, end, freq, dataset, stype_in, schema)
        return float(self.client.metadata.get_cost(**a))

    def load(self, symbol, start, end, freq, *, adjusted=True, dataset="GLBX.MDP3", stype_in="continuous",
             schema=None, max_cost_usd: float = 5.0, dry_run: bool = False, **_):
        a = self._args(symbol, start, end, freq, dataset, stype_in, schema)
        key = stable_hash({"v": 1, **{k: str(v) for k, v in a.items()}})
        cached = self.store_dir / f"{key}.parquet"
        if cached.exists():
            raw = pd.read_parquet(cached)
        else:
            cost = float(self.client.metadata.get_cost(**a))
            if cost > max_cost_usd:
                raise CostLimitExceeded(f"Databento estimated cost ${cost:.2f} exceeds max_cost_usd={max_cost_usd}; refusing to download")
            if dry_run:
                raise CostLimitExceeded(f"dry_run: estimated cost ${cost:.4f} (below limit {max_cost_usd}); not downloading")
            store = self.client.timeseries.get_range(**a)
            raw = store.to_df()  # ts_event index = bar OPEN (UTC)
            self.store_dir.mkdir(parents=True, exist_ok=True)
            raw.to_parquet(cached)
        raw = raw.reset_index().rename(columns={"index": "ts_event"}) if raw.index.name in (None, "ts_event") and "ts_event" not in raw.columns else raw
        pre = {"ts_col": "ts_event", "tz": "UTC", "stamp": "start"}
        df = normalise_table(raw, freq, pre, {})
        return clip_range(df, start, end)
