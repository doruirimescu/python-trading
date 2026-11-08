#!/usr/bin/env python
"""Download Databento GLBX.MDP3 data in resumable monthly chunks, cost-budgeted.

  .venv/bin/python scripts/databento_download.py download NQ.v.0 --schema ohlcv-1m --start 2010-06-06 --max-cost-usd 20
  .venv/bin/python scripts/databento_download.py download MNQ.v.0 --schema trades --start 2019-05-06 \
      --daily-window 09:00-11:30 --max-cost-usd 100 [--dry-run]
  .venv/bin/python scripts/databento_download.py merge NQ.v.0 --schema ohlcv-1m     # -> data_store/databento/NQ_1m.parquet
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradelab.data.sources.databento import BudgetExceeded, DatabentoDownloader, merge_chunks  # noqa: E402


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download")
    d.add_argument("symbol")
    d.add_argument("--schema", default="ohlcv-1m", choices=["ohlcv-1m", "ohlcv-1s", "ohlcv-1h", "ohlcv-1d", "trades"])
    d.add_argument("--start", default=None, help="YYYY-MM-DD (default: dataset start)")
    d.add_argument("--end", default=None, help="YYYY-MM-DD inclusive (default: yesterday UTC)")
    d.add_argument("--max-cost-usd", type=float, required=True, help="per-run budget; aborts BEFORE exceeding")
    d.add_argument("--daily-window", default=None, help="ET window per weekday, e.g. 09:00-11:30 (cuts billed bytes)")
    d.add_argument("--tod-window", default=None, help="ET filter after download (storage only), e.g. 08:30-12:00")
    d.add_argument("--no-footprint", action="store_true")
    d.add_argument("--root", default="data_store/databento")
    d.add_argument("--dataset", default="GLBX.MDP3")
    d.add_argument("--dry-run", action="store_true", help="cost-check chunks only; no download")
    m = sub.add_parser("merge")
    m.add_argument("symbol")
    m.add_argument("--schema", default="ohlcv-1m")
    m.add_argument("--footprint", action="store_true")
    m.add_argument("--out", default=None)
    m.add_argument("--root", default="data_store/databento")
    a = ap.parse_args(argv)

    if a.cmd == "merge":
        print(merge_chunks(a.root, a.symbol, a.schema, a.out, footprint=a.footprint))
        return 0
    if client is None:
        if not os.environ.get("DATABENTO_API_KEY"):
            print("DATABENTO_API_KEY is not set; nothing to do.", file=sys.stderr)
            return 3
        import databento as db
        client = db.Historical(os.environ["DATABENTO_API_KEY"])
    import pandas as pd
    dl = DatabentoDownloader(client, Path(a.root), a.dataset, a.max_cost_usd, daily_window=a.daily_window,
                             tod_window=a.tod_window, footprint_freq=None if a.no_footprint else "5min")
    start = a.start or dl.dataset_start().strftime("%Y-%m-%d")
    end = a.end or (pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        dl.download(a.symbol, a.schema, start, end, dry_run=a.dry_run)
    except BudgetExceeded as e:
        print(f"BUDGET: {e}", file=sys.stderr)
        print(f"running total ${dl.total_cost:.4f}")
        return 5
    print(f"done. total ${dl.total_cost:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
