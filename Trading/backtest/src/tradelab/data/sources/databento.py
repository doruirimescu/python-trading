"""Databento acquisition pipeline: monthly, resumable, cost-budgeted downloads of GLBX.MDP3 continuous data.

Layout (relative to ``root``, default ``data_store/databento``)::

    <dataset>/<schema>/<symbol>/YYYY-MM.parquet            # ohlcv-1m bars, or trades->1m order-flow bars
    <dataset>/trades/<symbol>/footprint5m/YYYY-MM.parquet  # optional price-level volume (ts, price, bid_vol, ask_vol)
    <dataset>/<schema>/<symbol>/YYYY-MM.partial.parquet    # month not yet complete; re-fetched on next run

Chunk files carry ``ts_event`` (bar OPEN, UTC), OHLCV, ``instrument_id`` and ``contract`` (raw contract symbol such
as ``NQZ4``, resolved from Databento symbology) so roll boundaries are visible. For ``trades`` the raw ticks are
aggregated on the fly (see ``orderflow_bars``); raw trades are not stored. Never calls the network unless the
supplied client does; tests use a fake client. NO download happens in ``estimate``/``plan`` paths.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ..calendar import ET
from ..orderflow_bars import (
    aggregate_trades,
    atomic_to_parquet,
    combine_bars,
    combine_footprint,
    parse_window,
    write_footprint_parquet,
)
from .databento_src import CostLimitExceeded

DATASET = "GLBX.MDP3"
OHLCV_COLS = ["open", "high", "low", "close", "volume"]


class BudgetExceeded(CostLimitExceeded):
    """Raised BEFORE a chunk is downloaded when it would push the run past ``max_cost_usd``."""


# ----------------------------------------------------------------------------------------------- chunking
def month_chunks(start, end) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """[start, end] inclusive dates -> UTC calendar-month chunks [lo, hi) clipped to the range."""
    lo = pd.Timestamp(start).tz_localize(None).normalize()
    hi = pd.Timestamp(end).tz_localize(None).normalize() + pd.Timedelta(days=1)
    out, cur = [], lo
    while cur < hi:
        nxt = min((cur.replace(day=1) + pd.offsets.MonthBegin(1)), hi)
        out.append((cur.tz_localize("UTC"), nxt.tz_localize("UTC")))
        cur = nxt
    return out


def day_windows(lo: pd.Timestamp, hi: pd.Timestamp, window) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Per-weekday ET time-of-day windows inside [lo, hi), returned as UTC (DST-safe)."""
    a, b = parse_window(window)
    ha, hb = pd.Timedelta(hours=int(a[:2]), minutes=int(a[3:5])), pd.Timedelta(hours=int(b[:2]), minutes=int(b[3:5]))
    out = []
    for d in pd.date_range(lo.tz_localize(None).normalize(), hi.tz_localize(None) - pd.Timedelta(seconds=1), freq="D"):
        if d.dayofweek >= 5:
            continue
        s = (d + ha).tz_localize(ET).tz_convert("UTC")
        e = (d + hb).tz_localize(ET).tz_convert("UTC")
        if e > lo and s < hi:
            out.append((max(s, lo), min(e, hi)))
    return out


def symbol_dir_name(symbol: str) -> str:
    return symbol.replace("/", "_")


def _iso(ts: pd.Timestamp) -> str:
    return ts.tz_convert("UTC").isoformat()


# ----------------------------------------------------------------------------------------------- downloader
@dataclass
class ChunkReport:
    month: str
    status: str            # downloaded | skipped | dry_run | empty
    cost_usd: float = 0.0
    rows: int = 0
    path: str = ""


@dataclass
class DatabentoDownloader:
    client: object
    root: Path = Path("data_store/databento")
    dataset: str = DATASET
    max_cost_usd: float = 5.0
    stype_in: str = "continuous"
    daily_window: str | None = None          # ET "HH:MM-HH:MM": request only this window per weekday (cuts billing)
    tod_window: str | None = None            # ET filter applied after download (storage only; no billing effect)
    footprint_freq: str | None = "5min"      # trades only; None disables footprint
    batch_rows: int = 2_000_000
    now: pd.Timestamp | None = None          # injectable clock (tests)
    log: object = print
    total_cost: float = field(default=0.0, init=False)
    reports: list = field(default_factory=list, init=False)

    # -- paths
    def schema_dir(self, symbol: str, schema: str) -> Path:
        return Path(self.root) / self.dataset / schema / symbol_dir_name(symbol)

    def chunk_path(self, symbol, schema, lo: pd.Timestamp, partial=False) -> Path:
        return self.schema_dir(symbol, schema) / f"{lo:%Y-%m}{'.partial' if partial else ''}.parquet"

    def footprint_path(self, symbol, lo: pd.Timestamp, partial=False) -> Path:
        return self.schema_dir(symbol, "trades") / "footprint5m" / f"{lo:%Y-%m}{'.partial' if partial else ''}.parquet"

    # -- metadata (free)
    def dataset_start(self) -> pd.Timestamp:
        r = self.client.metadata.get_dataset_range(dataset=self.dataset)
        t = pd.Timestamp(r["start"])
        return t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")

    def _ranges(self, lo, hi) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        return day_windows(lo, hi, self.daily_window) if self.daily_window else [(lo, hi)]

    def chunk_cost(self, symbol, schema, lo, hi) -> float:
        total = 0.0
        for s, e in self._ranges(lo, hi):
            total += float(self.client.metadata.get_cost(
                dataset=self.dataset, symbols=[symbol], schema=schema, stype_in=self.stype_in,
                start=_iso(s), end=_iso(e)))
        return total

    # -- contract resolution (free symbology call)
    def contract_map(self, symbol, lo, hi) -> list[tuple[pd.Timestamp, str]]:
        try:
            res = self.client.symbology.resolve(
                dataset=self.dataset, symbols=[symbol], stype_in=self.stype_in, stype_out="raw_symbol",
                start_date=lo.strftime("%Y-%m-%d"), end_date=hi.strftime("%Y-%m-%d"))
            ivs = res["result"].get(symbol, [])
            return sorted((pd.Timestamp(i["d0"]).tz_localize("UTC"), str(i["s"])) for i in ivs)
        except Exception as exc:  # noqa: BLE001 - symbology is best-effort; instrument_id still identifies rolls
            self.log(f"  [warn] symbology.resolve failed ({exc}); contract falls back to instrument_id")
            return []

    @staticmethod
    def attach_contract(bars: pd.DataFrame, cmap: list[tuple[pd.Timestamp, str]], ts_col: str = "ts_event") -> pd.DataFrame:
        """Add ``contract`` per bar from interval map keyed on the UTC date of bar open; fallback str(instrument_id)."""
        out = bars.copy()
        fallback = out["instrument_id"].astype("int64").astype(str).to_numpy() if "instrument_id" in out else np.array([""] * len(out))
        if cmap and len(out):
            starts = pd.DatetimeIndex([c[0] for c in cmap])
            names = np.array([c[1] for c in cmap], dtype=object)
            pos = starts.searchsorted(pd.DatetimeIndex(out[ts_col]).normalize(), side="right") - 1
            con = np.where(pos >= 0, names[np.clip(pos, 0, None)], fallback)
            out["contract"] = con
        else:
            out["contract"] = fallback
        return out

    # -- fetching
    def _fetch_ohlcv(self, symbol, schema, lo, hi) -> pd.DataFrame:
        parts = []
        for s, e in self._ranges(lo, hi):
            store = self.client.timeseries.get_range(
                dataset=self.dataset, symbols=[symbol], schema=schema, stype_in=self.stype_in,
                start=_iso(s), end=_iso(e))
            df = store.to_df()
            if len(df):
                parts.append(df)
        if not parts:
            return pd.DataFrame(columns=["ts_event"] + OHLCV_COLS + ["instrument_id"])
        df = pd.concat(parts)
        if "ts_event" not in df.columns:
            df = df.reset_index().rename(columns={df.index.name or "index": "ts_event"})
        keep = ["ts_event"] + OHLCV_COLS + ["instrument_id"]
        return df[keep].sort_values("ts_event", kind="stable").drop_duplicates("ts_event").reset_index(drop=True)

    def _fetch_trades(self, symbol, lo, hi):
        bars, fps = [], []
        for s, e in self._ranges(lo, hi):
            store = self.client.timeseries.get_range(
                dataset=self.dataset, symbols=[symbol], schema="trades", stype_in=self.stype_in,
                start=_iso(s), end=_iso(e))
            res = store.to_df(count=self.batch_rows) if self.batch_rows else store.to_df()
            for piece in ([res] if isinstance(res, pd.DataFrame) else res):
                if len(piece) == 0:
                    continue
                r = aggregate_trades(piece, freq="1min", footprint_freq=self.footprint_freq, tod_window=self.tod_window)
                bars.append(r.bars)
                if r.footprint is not None:
                    fps.append(r.footprint)
        return combine_bars(bars), (combine_footprint(fps) if self.footprint_freq else None)

    # -- main entry
    def download(self, symbol: str, schema: str, start, end, *, dry_run: bool = False) -> list[ChunkReport]:
        if schema not in ("ohlcv-1m", "ohlcv-1s", "ohlcv-1h", "ohlcv-1d", "trades"):
            raise ValueError(f"unsupported schema {schema}")
        now = (self.now or pd.Timestamp.now(tz="UTC")).tz_convert("UTC")
        complete_before = now.normalize() - pd.Timedelta(days=1)   # data older than yesterday is final
        reports = []
        for lo, hi in month_chunks(start, end):
            tag = f"{lo:%Y-%m}"
            final = self.chunk_path(symbol, schema, lo)
            if final.exists():
                reports.append(ChunkReport(tag, "skipped", path=str(final)))
                self.log(f"[{tag}] exists, skip")
                continue
            cost = self.chunk_cost(symbol, schema, lo, hi)
            if self.total_cost + cost > self.max_cost_usd + 1e-12:
                raise BudgetExceeded(
                    f"[{tag}] chunk ${cost:.4f} would raise running total ${self.total_cost:.4f} past "
                    f"--max-cost-usd {self.max_cost_usd}; stopping before download (completed chunks are kept)")
            if dry_run:
                self.total_cost += cost
                reports.append(ChunkReport(tag, "dry_run", cost))
                self.log(f"[{tag}] dry-run cost ${cost:.4f}  running ${self.total_cost:.4f}")
                continue
            month_end = lo.replace(day=1) + pd.offsets.MonthBegin(1)
            partial = hi < month_end or hi > complete_before + pd.Timedelta(days=1)  # clipped range or live month
            cmap = self.contract_map(symbol, lo, hi)
            if schema == "trades":
                bars, fp = self._fetch_trades(symbol, lo, hi)
                bars = bars.reset_index()
                bars.insert(0, "ts_event", bars.pop("ts") - pd.Timedelta("1min"))
                bars = self.attach_contract(bars, cmap)
                if fp is not None:
                    write_footprint_parquet(fp, self.footprint_path(symbol, lo, partial))
                frame = bars
            else:
                frame = self.attach_contract(self._fetch_ohlcv(symbol, schema, lo, hi), cmap)
            path = self.chunk_path(symbol, schema, lo, partial)
            atomic_to_parquet(frame, path, compression="zstd")
            if not partial:  # a finished month supersedes its earlier .partial files
                for p in (self.chunk_path(symbol, schema, lo, True), self.footprint_path(symbol, lo, True)):
                    p.unlink(missing_ok=True)
            self.total_cost += cost
            reports.append(ChunkReport(tag, "downloaded" if len(frame) else "empty", cost, len(frame), str(path)))
            self.log(f"[{tag}] {len(frame)} rows, ${cost:.4f}  running ${self.total_cost:.4f} / ${self.max_cost_usd}")
        self.reports.extend(reports)
        return reports


# ----------------------------------------------------------------------------------------------- merge
def merge_chunks(root, symbol: str, schema: str = "ohlcv-1m", out: str | Path | None = None, *,
                 dataset: str = DATASET, footprint: bool = False) -> Path:
    """Concatenate monthly chunks (incl. .partial) into one parquet loadable via ``preset: databento_ohlcv_1m``."""
    d = Path(root) / dataset / schema / symbol_dir_name(symbol)
    if footprint:
        d = d / "footprint5m"
    files = sorted(d.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no chunks under {d}")
    # prefer final over .partial for the same month
    by_month = {}
    for f in files:
        by_month.setdefault(f.name.split(".")[0], []).append(f)
    chosen = [sorted(v, key=lambda p: "partial" in p.name)[0] for _, v in sorted(by_month.items())]
    df = pd.concat([pd.read_parquet(f) for f in chosen], ignore_index=True)
    key = ["ts", "price"] if footprint else ["ts_event"]
    df = df.sort_values(key, kind="stable").drop_duplicates(key, keep="last").reset_index(drop=True)
    if out is None:
        base = symbol.split(".")[0]
        suffix = "_1m" + ("" if schema.startswith("ohlcv") else "_orderflow")
        out = Path(root) / (f"{base}{suffix}_footprint5m.parquet" if footprint else f"{base}{suffix}.parquet")
    atomic_to_parquet(df, Path(out), compression="zstd")
    return Path(out)


def now_utc() -> pd.Timestamp:
    return pd.Timestamp(time.time(), unit="s", tz="UTC")
