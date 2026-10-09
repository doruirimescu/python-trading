# export_trend.py
"""
Publish the trend-filtered sector portfolio research for the Basket Rotation site.

Runs mrscore.backtest.trend_portfolio from config_trend.yaml: the strategy, an
unfiltered equal-weight version, the benchmark, leverage variants and an SMA
lookback sweep, and writes one script-registered JSON file the research page loads:

    <out>/trend_research.js    window.nexusData["trend_research"] = {...}

<out> defaults to $BASKET_SITE_DATA, else ~/personal/stock-market-data/docs/basket/data.

Usage (from the basket/ folder):
    PYTHONPATH=src python3 -m mrscore.cli.export_trend
    PYTHONPATH=src python3 -m mrscore.cli.export_trend --config config_trend.yaml --out some/dir
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np

from mrscore.backtest.trend_portfolio import month_end_mask, performance, run_trend_portfolio
from mrscore.cli.export_web import DEFAULT_OUT, _num, _series, _write_js
from mrscore.config.loader import load_trend_config
from mrscore.io.adapters import build_price_panel
from mrscore.io.history import OHLC
from mrscore.io.yfinance_loader import YFinanceLoader, YFinanceLoadRequest
from mrscore.utils.logging import get_logger

logger = get_logger(__name__)

NO_FILTER_SMA = 10**6  # never enough month-ends: every asset stays "on"


def load_panel(cfg):
    p = cfg.trend_portfolio
    symbols = list(dict.fromkeys(cfg.data.tickers + [p.risk_off] + [s for s in (cfg.benchmark, p.cash_rate) if s]))
    histories = YFinanceLoader().load(
        YFinanceLoadRequest(
            tickers=symbols,
            period=cfg.data.period,
            interval=cfg.data.interval,
            auto_adjust=True,
            ending_date=cfg.data.ending_date,
            cache_enabled=cfg.data.cache.enabled,
            cache_path=cfg.data.cache.path,
        )
    )
    # Union + forward-fill so a missing quote in one series (e.g. the yield) drops no days.
    panel = build_price_panel(histories=histories, symbols=symbols, field=OHLC.CLOSE, align="union",
                              normalize_by_first=False, union_fill="ffill")
    ok = np.isfinite(panel.values).all(axis=1)
    first = int(np.argmax(ok))
    return panel.dates[first:], symbols, panel.values[first:]


def _window(dates, start, end=None):
    d = dates.astype("datetime64[D]")
    m = d >= np.datetime64(start) if start else np.ones(len(d), dtype=bool)
    if end:
        m &= d < np.datetime64(end)
    return m


def build_research(config_path: Path) -> dict:
    cfg = load_trend_config(config_path)
    p, r = cfg.trend_portfolio, cfg.research
    dates, symbols, values = load_panel(cfg)
    col = {s: i for i, s in enumerate(symbols)}
    prices = values[:, [col[s] for s in cfg.data.tickers]]
    risk_off = values[:, col[p.risk_off]]
    cash = values[:, col[p.cash_rate]] if p.cash_rate else None
    bench = values[:, col[cfg.benchmark]] if cfg.benchmark else None

    def run(**kw):
        return run_trend_portfolio(prices=prices, risk_off=risk_off, dates=dates, params=p, cash_rate_pct=cash, **kw)

    main = run()
    curves = {"strategy": main.equity, "equal_weight": run(sma_months=NO_FILTER_SMA).equity}
    if bench is not None:
        curves["benchmark"] = bench
    for L in r.leverage_sweep:
        curves[f"leverage_{L:g}"] = run(leverage=L).equity

    ev = _window(dates, r.evaluate_from)
    e_dates = dates[ev]
    e_cash = cash[ev] if cash is not None else None
    windows = {"full": (r.evaluate_from, None)}
    if r.split_date:
        windows["first"] = (r.evaluate_from, r.split_date)
        windows["second"] = (r.split_date, None)

    def stats(equity):
        out = {}
        for name, (a, b) in windows.items():
            m = _window(dates, a, b)
            out[name] = {k: _num(v, 6) for k, v in performance(equity[m], dates[m], cash[m] if cash is not None else None).items()}
        return out

    sweep = []
    for n in r.sma_months_sweep:
        eq = main.equity if n == p.sma_months else run(sma_months=n).equity
        sweep.append({"sma_months": n, **stats(eq)})

    me = month_end_mask(dates)
    # The final bar is flagged as a month-end only because the data stops there; unless it
    # is the month's last business day, its signal is a mid-month preview, not official.
    final = np.datetime64(str(dates[-1])[:10])
    month_complete = np.busday_offset(final, 1, roll="forward").astype("datetime64[M]") != final.astype("datetime64[M]")
    official = [s for s in main.signals if s.index < len(dates) - 1 or month_complete]
    signals = [s for s in official if ev[s.index]]

    def snapshot(sig):
        idx = np.flatnonzero(me[: sig.index + 1])[-p.sma_months:]
        return {
            "date": str(dates[sig.index])[:10],
            "on": [bool(x) for x in sig.on],
            "close": _series(prices[sig.index], 6),
            "sma": _series(prices[idx].mean(axis=0), 6),
            "weights": _series(sig.weights, 6),
        }

    text = Path(config_path).read_text(encoding="utf-8")
    created = datetime.now()
    return {
        "meta": {
            "created_at": created.isoformat(timespec="seconds"),
            "config_path": Path(config_path).name,
            "config_hash": hashlib.sha1(text.encode("utf-8")).hexdigest()[:10],
            "start": str(e_dates[0])[:10],
            "end": str(e_dates[-1])[:10],
            "split": str(r.split_date) if r.split_date else None,
            "data_start": str(dates[0])[:10],
        },
        "config": cfg.model_dump(mode="json"),
        "config_yaml": text,
        "assets": cfg.data.tickers,
        "dates": [str(d)[:10] for d in e_dates],
        # rebased to 1.0 at the start of the evaluation window
        "series": {k: _series(v[ev] / v[ev][0], 6) for k, v in curves.items()},
        "stats": {k: stats(v) for k, v in curves.items()},
        "sweep": sweep,
        "signals": {
            "dates": [str(dates[s.index])[:10] for s in signals],
            "on": ["".join("1" if x else "0" for x in s.on) for s in signals],
        },
        "current": snapshot(official[-1]),
        "preview": None if month_complete else snapshot(main.signals[-1]),
        "costs_total": _num(float(main.costs[ev].sum()), 6),
        "turnover_per_year": _num(float(main.turnover[ev].sum()) / performance(main.equity[ev], e_dates, e_cash)["years"], 6),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Export the trend-filtered portfolio research for the web UI")
    ap.add_argument("--config", default="config_trend.yaml")
    ap.add_argument("--out", default=DEFAULT_OUT, help="site data folder (default: %(default)s)")
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    data = build_research(Path(args.config))
    _write_js(out / "trend_research.js", "trend_research", data)
    s = data["stats"]
    logger.info("Strategy %s CAGR %.2f%% maxDD %.1f%% | benchmark CAGR %.2f%% maxDD %.1f%% -> %s",
                data["meta"]["start"], s["strategy"]["full"]["cagr"] * 100, s["strategy"]["full"]["max_dd"] * 100,
                s.get("benchmark", s["strategy"])["full"]["cagr"] * 100, s.get("benchmark", s["strategy"])["full"]["max_dd"] * 100, out)


if __name__ == "__main__":
    main()
