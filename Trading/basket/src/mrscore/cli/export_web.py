# export_web.py
"""
Publish a ratio-universe run for the Basket Rotation pages of Investing Nexus.

Runs the same pipeline as main_2 (panel -> ratio jobs -> engine scan -> top-k ->
backtest) and writes a run snapshot the static pages can load. The pages live in the stock-market-data
repo (docs/basket/, served by GitHub Pages), so that is the default output:

    <out>/runs/<run_id>.js   one snapshot per run
    <out>/manifest.js        [{id, created_at, ...}] newest first

<out> defaults to $BASKET_SITE_DATA, else ~/personal/stock-market-data/docs/basket/data.

Each file is the JSON payload behind a one-line registration,
    window.nexusData = window.nexusData || {}; window.nexusData["<key>"] = {...};
so the pages can load it with a <script> tag. Unlike fetch(), that also works
when the HTML is opened straight from disk (file://).

Usage (from the basket/ folder):
    PYTHONPATH=src python3 -m mrscore.cli.export_web
    PYTHONPATH=src python3 -m mrscore.cli.export_web --config config.yaml --out some/dir
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from mrscore.app.composition_root import build_app
from mrscore.cli.main_2 import (
    _compute_returns_inplace,
    _job_to_ratio_spec,
    load_price_panel,
    load_ratio_jobs,
)
from mrscore.config.loader import load_config
from mrscore.core.ranking import TopKRanker
from mrscore.core.ratio_universe import RatioUniverse
from mrscore.io.adapters import AlignedPanel
from mrscore.utils.logging import get_logger

logger = get_logger(__name__)

MANIFEST_KEEP = 50  # newest runs listed in the manifest
MANIFEST_KEY = "basket_manifest"  # distinct from the valuation pages' "manifest"
DEFAULT_OUT = os.environ.get("BASKET_SITE_DATA", "~/personal/stock-market-data/docs/basket/data")


def _num(x, sig: int | None = None):
    """JSON-safe float: NaN/inf -> None, optionally rounded to `sig` significant digits."""
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        return None
    if sig is not None and x != 0.0:
        return float(f"{x:.{sig}g}")
    return x


def _series(values, sig: int = 7) -> list:
    return [_num(v, sig) for v in values]


def _date(value) -> str | None:
    if value is None:
        return None
    return str(np.datetime_as_string(value, unit="D")) if isinstance(value, np.datetime64) else str(value)[:10]


def _trace_arrays(T: int):
    mean = np.full(T, np.nan)
    vol = np.full(T, np.nan)
    z = np.full(T, np.nan)

    def on_bar(t: int, m: float, v: float, zz: float) -> None:
        mean[t] = m
        vol[t] = v
        z[t] = zz

    return mean, vol, z, on_bar


def _returns_for(series: np.ndarray, returns_mode: str, vol_unit: str):
    if vol_unit != "returns":
        return None
    T = series.shape[0]
    out = np.empty(T - 1, dtype=np.float64)
    tmp = np.empty(T - 1, dtype=np.float64) if returns_mode == "log" else None
    return _compute_returns_inplace(prices=series, returns_out=out, tmp_out=tmp, mode=returns_mode)


def _export_events(result) -> list[dict]:
    return [
        {
            "dir": e.direction.value,
            "status": e.status.value,
            "s": int(e.start_index),
            "e": int(e.end_index),
            "dur": int(e.duration),
            "start_z": _num(e.start_zscore, 6),
            "max_abs_z": _num(e.max_abs_zscore, 6),
            "start_price": _num(e.start_price, 8),
            "end_price": _num(e.end_price, 8),
            "start_vol": _num(e.start_volatility, 6),
        }
        for e in (result.events or [])
    ]


def _export_trades(result, raw_panel: AlignedPanel, spec) -> list[dict]:
    num_idx = [int(i) for i in spec.numerator.indices]
    den_idx = [int(i) for i in spec.denominator.indices]
    rows = []
    for tr in result.trades or []:
        legs = []
        for idxs, qtys in ((num_idx, tr.qty_num), (den_idx, tr.qty_den)):
            for col, qty in zip(idxs, qtys if qtys is not None else []):
                if qty == 0.0:
                    continue
                legs.append(
                    {
                        "sym": raw_panel.symbols[col],
                        "side": "BUY" if qty > 0 else "SELL",
                        "qty": _num(qty, 10),
                        "entry_px": _num(raw_panel.values[tr.entry_index, col], 10),
                        "exit_px": _num(raw_panel.values[tr.exit_index, col], 10),
                    }
                )
        costs = float(tr.costs)
        rows.append(
            {
                "leg": "num" if tr.direction.value == "up" else "den",
                "dir": tr.direction.value,
                "s": int(tr.entry_index),
                "e": int(tr.exit_index),
                "dur": int(tr.duration),
                "gross_entry": _num(tr.gross_notional_entry, 10),
                "gross_exit": _num(tr.gross_notional_exit, 10),
                "pnl": _num(tr.pnl, 10),
                "costs": _num(costs, 10),
                "net": _num(float(tr.pnl) - costs, 10),
                "legs": legs,
            }
        )
    return rows


def build_run(config_path: Path) -> dict:
    t0 = time.perf_counter()
    cfg = load_config(config_path)
    app = build_app(cfg)
    engine = app.engine

    returns_mode = cfg.data.returns_mode
    vol_unit = cfg.volatility_estimator.params.volatility_unit

    panel_raw, panel_key = load_price_panel(cfg)
    panel_for_ru = AlignedPanel(dates=panel_raw.dates, symbols=panel_raw.symbols, values=panel_raw.values.copy())
    ru = RatioUniverse(panel=panel_for_ru, normalize_by_first=True, eps=1e-12)
    ratio_cfg = cfg.ratio_universe
    jobs = load_ratio_jobs(cfg, ru, panel_key)
    top_k = cfg.visualization.top_k or 10

    T = len(ru.dates)
    dates = ru.dates

    # --- full scan: keep a compact score row per job, plus a streaming top-k ---
    ranker = TopKRanker(top_k)
    buf = np.empty(T, dtype=np.float64)
    scan = {"num_id": [], "den_id": [], "score": [], "events": [], "reverted": []}
    for job in jobs:
        ru.compute_ratio_series_into(buf, job)
        result = engine.run(prices=buf, returns=_returns_for(buf, returns_mode, vol_unit), dates=dates)
        score = float(result.score)
        scan["num_id"].append(job.num_id)
        scan["den_id"].append(job.den_id)
        scan["score"].append(_num(score, 8))
        scan["events"].append(result.total_events)
        scan["reverted"].append(result.reverted_events)
        if math.isfinite(score):
            ranker.consider(job=job, score=score)
    t_scan = time.perf_counter() - t0
    logger.info("Scanned %d jobs in %.1fs", len(jobs), t_scan)

    lib_num = ru.get_basket_library(ratio_cfg.k_num)
    lib_den = ru.get_basket_library(ratio_cfg.k_den)

    # --- top-k deep dive: engine trace + events, backtest trace + trades + equity ---
    top = []
    for rank, ranked in enumerate(ranker.items_sorted(descending=True), start=1):
        job = ranked.job
        spec, job_id = _job_to_ratio_spec(ru, job)
        num_syms, den_syms = ru.job_to_symbols(job)

        ratio = ru.compute_ratio_series(job)
        e_mean, e_vol, e_z, e_hook = _trace_arrays(T)
        er = engine.run(prices=ratio, returns=_returns_for(ratio, returns_mode, vol_unit), dates=dates, on_bar=e_hook)

        entry = {
            "rank": rank,
            "job_id": job_id,
            "num_id": job.num_id,
            "den_id": job.den_id,
            "num": list(num_syms),
            "den": list(den_syms),
            "num_idx": [int(i) for i in spec.numerator.indices],
            "den_idx": [int(i) for i in spec.denominator.indices],
            "score": _num(ranked.score, 10),
            "engine": {
                "total": er.total_events,
                "reverted": er.reverted_events,
                "failed": er.failed_events,
                "expired": er.expired_events,
                "sharpe": _num(er.sharpe, 8),
                "by_direction": {k: _num(v, 6) for k, v in (er.by_direction or {}).items()},
                "by_volatility_bucket": {k: _num(v, 6) for k, v in (er.by_volatility_bucket or {}).items()},
                "events": _export_events(er),
                "trace": {"ratio": _series(ratio, 8), "mean": _series(e_mean), "vol": _series(e_vol), "z": _series(e_z, 5)},
            },
            "backtest": None,
        }

        if app.backtester is not None:
            b_mean, b_vol, b_z, b_hook = _trace_arrays(T)
            br = app.backtester.run_one(panel=panel_for_ru, ratio_spec=spec, job_id=job_id, on_bar=b_hook)
            curve = br.equity_curve or []
            entry["backtest"] = {
                "initial_cash": _num(br.initial_cash),
                "final_equity": _num(br.final_equity, 10),
                "total_return": _num(br.total_return, 10),
                "trades": _export_trades(br, panel_raw, spec),
                "equity": {"i": [int(p.index) for p in curve], "v": [_num(p.equity, 9) for p in curve]},
                "trace": {"mean": _series(b_mean), "vol": _series(b_vol), "z": _series(b_z, 5)},
            }
        top.append(entry)

    config_text = Path(config_path).read_text(encoding="utf-8")
    created = datetime.now()
    return {
        "meta": {
            "id": created.strftime("%Y-%m-%d_%H%M%S"),
            "created_at": created.isoformat(timespec="seconds"),
            "config_path": str(config_path),
            "config_hash": hashlib.sha1(config_text.encode("utf-8")).hexdigest()[:10],
            "panel_key": panel_key,
            "elapsed_s": round(time.perf_counter() - t0, 2),
            "scan_s": round(t_scan, 2),
            "T": T,
            "N": len(ru.symbols),
            "jobs": len(jobs),
            "jobs_upper_bound": ru.estimate_ratio_count(
                k_num=ratio_cfg.k_num,
                k_den=ratio_cfg.k_den,
                unordered_if_equal_k=ratio_cfg.unordered_if_equal_k,
                disallow_overlap=ratio_cfg.disallow_overlap,
            ),
            "top_k": top_k,
        },
        "config": cfg.model_dump(mode="json"),
        "config_yaml": config_text,
        "panel": {
            "dates": [_date(d) for d in panel_raw.dates],
            "symbols": list(panel_raw.symbols),
            # column-major raw closes at full precision (the in-browser lab re-runs on these)
            "close": [[_num(v) for v in panel_raw.values[:, j]] for j in range(panel_raw.values.shape[1])],
        },
        "baskets": {
            "num": lib_num.baskets.tolist(),
            "den": lib_den.baskets.tolist(),
        },
        "scan": scan,
        "top": top,
    }


def _write_js(path: Path, key: str, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    path.write_text(f'window.nexusData=window.nexusData||{{}};window.nexusData["{key}"]={payload};\n', encoding="utf-8")


def _read_registered(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text[text.index("]=") + 2 : text.rstrip().rindex(";")])


def write_manifest(out_dir: Path) -> list[dict]:
    """Rebuild manifest.js from the run files on disk (newest first)."""
    runs = []
    for p in sorted((out_dir / "runs").glob("*.js"), reverse=True)[:MANIFEST_KEEP]:
        run = _read_registered(p)
        m = run["meta"]
        best = run["top"][0] if run["top"] else None
        runs.append(
            {
                "id": m["id"],
                "created_at": m["created_at"],
                "config_hash": m["config_hash"],
                "tickers": run["panel"]["symbols"],
                "jobs": m["jobs"],
                "top_score": best["score"] if best else None,
                "best_return": (best["backtest"] or {}).get("total_return") if best else None,
            }
        )
    _write_js(out_dir / "manifest.js", MANIFEST_KEY, runs)
    return runs


def main() -> None:
    ap = argparse.ArgumentParser(description="Export a basket run for the web UI")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default=DEFAULT_OUT, help="run data folder of the site (default: %(default)s)")
    ap.add_argument("--manifest-only", action="store_true", help="only rebuild manifest.js from the runs on disk")
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser()
    if args.manifest_only:
        logger.info("Rebuilt manifest: %d runs -> %s", len(write_manifest(out_dir)), out_dir)
        return
    run = build_run(Path(args.config))
    run_id = run["meta"]["id"]
    _write_js(out_dir / "runs" / f"{run_id}.js", f"runs/{run_id}", run)
    runs = write_manifest(out_dir)
    logger.info("Published run %s (%d runs in manifest) -> %s", run_id, len(runs), out_dir)


if __name__ == "__main__":
    main()
