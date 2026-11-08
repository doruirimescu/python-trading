#!/usr/bin/env python
"""Databento cost planner (metadata only; never downloads). Prints a markdown table.

  .venv/bin/python scripts/databento_plan.py [--daily-window 09:00-11:30] [--samples 6] [--exact-window]

Without DATABENTO_API_KEY it only prints the plan (what it WOULD query). Windowed cost is estimated as
(full-range cost) x (windowed/full cost ratio on N sampled weekdays); --exact-window sums get_cost over every weekday
(thousands of free metadata calls).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradelab.data.sources.databento import DATASET, day_windows  # noqa: E402

JOBS = [  # (label, symbol, schema, start, windowed?)
    ("a", "NQ.v.0", "ohlcv-1m", None, False),
    ("b", "MNQ.v.0", "ohlcv-1m", "2019-05-01", False),
    ("c", "MNQ.v.0", "trades", "2019-05-01", True),
    ("d1", "NQ.v.0", "trades", None, True),
    ("d2", "NQ.v.0", "trades", "2019-05-01", True),
]


def _cost(client, symbol, schema, s, e, dataset=DATASET) -> float:
    return float(client.metadata.get_cost(dataset=dataset, symbols=[symbol], schema=schema, stype_in="continuous",
                                          start=s.isoformat(), end=e.isoformat()))


def window_cost(client, symbol, schema, lo, hi, window, samples=6, exact=False) -> tuple[float, str]:
    wins = day_windows(lo, hi, window)
    if exact or len(wins) <= samples:
        return sum(_cost(client, symbol, schema, s, e) for s, e in wins), "exact"
    idx = sorted({int(round(i)) for i in pd.Series(range(samples)).mul((len(wins) - 1) / (samples - 1))})
    pick = [wins[i] for i in idx]
    w = sum(_cost(client, symbol, schema, s, e) for s, e in pick)
    f = sum(_cost(client, symbol, schema, s.normalize(), s.normalize() + pd.Timedelta(days=1)) for s, _ in pick)
    ratio = w / f if f else float("nan")
    full = _cost(client, symbol, schema, lo, hi)
    return full * ratio, f"est. ratio {ratio:.3f} over {len(pick)} days"


def plan_rows(client, window="09:00-11:30", samples=6, exact=False, end=None):
    r = client.metadata.get_dataset_range(dataset=DATASET)
    ds_start = pd.Timestamp(r["start"]).tz_convert("UTC") if pd.Timestamp(r["start"]).tzinfo else pd.Timestamp(r["start"]).tz_localize("UTC")
    hi = pd.Timestamp(end).tz_localize("UTC") if end else (pd.Timestamp(r["end"]).tz_convert("UTC") if pd.Timestamp(r["end"]).tzinfo else pd.Timestamp(r["end"]).tz_localize("UTC")).normalize()
    rows = [("-", "GLBX.MDP3 dataset start", "", "", f"{ds_start:%Y-%m-%d}", "", "")]
    for label, sym, schema, start, windowed in JOBS:
        lo = pd.Timestamp(start).tz_localize("UTC") if start else ds_start.normalize()
        full = _cost(client, sym, schema, lo, hi)
        rows.append((label, sym, schema, f"{lo:%Y-%m-%d}..{hi:%Y-%m-%d}", "full 24h", f"{full:,.2f}", ""))
        if windowed:
            c, note = window_cost(client, sym, schema, lo, hi, window, samples, exact)
            rows.append((label, sym, schema, f"{lo:%Y-%m-%d}..{hi:%Y-%m-%d}", f"daily {window} ET", f"{c:,.2f}", note))
    return rows


def render(rows) -> str:
    out = ["| Job | Symbol | Schema | Range | Mode | Est. cost USD | Note |", "|---|---|---|---|---|---|---|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def offline_plan(window) -> str:
    lines = ["DATABENTO_API_KEY not set: showing plan only (no calls made).", ""]
    lines += ["1. metadata.get_dataset_range(GLBX.MDP3) -> start date (expected ~2010-06-06)"]
    for label, sym, schema, start, windowed in JOBS:
        lines.append(f"- ({label}) get_cost {sym} {schema} from {start or 'dataset start'} to present"
                     + (f", full vs daily {window} ET windows (sampled ratio)" if windowed else ""))
    return "\n".join(lines)


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-window", default="09:00-11:30")
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--exact-window", action="store_true")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (default: dataset range end)")
    a = ap.parse_args(argv)
    if client is None:
        if not os.environ.get("DATABENTO_API_KEY"):
            print(offline_plan(a.daily_window))
            return 0
        import databento as db
        client = db.Historical(os.environ["DATABENTO_API_KEY"])
    print(render(plan_rows(client, a.daily_window, a.samples, a.exact_window, a.end)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
