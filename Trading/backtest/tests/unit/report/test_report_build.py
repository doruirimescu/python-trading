import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "golden"))
from synth import make_result, result_from_returns  # noqa: E402

from tradelab.report import (SECTION_REGISTRY, Section, build_compare_report, build_run_report, make_run_dir,  # noqa: E402
                             register_section, update_latest)
from tradelab.robustness import run_grid, walk_forward  # noqa: E402

RES = make_result(n_days=520)
DAYS = RES.returns_daily.index
NOISE = RES.returns_daily - 0.0006


def run_fn(params, *, start=None, end=None, cost_mult=1.0):
    k = params.get("k", 5)
    r = NOISE + 0.0012 * max(0.0, 1 - abs(k - 5) / 5) - 0.0002 * cost_mult
    if start is not None:
        r = r[r.index >= pd.Timestamp(start)]
    if end is not None:
        r = r[r.index <= pd.Timestamp(end)]
    return result_from_returns(r, trades=RES.trades)


class FakePanel:
    def __init__(self):
        rng = np.random.default_rng(1)
        idx = pd.date_range("2024-01-02 14:00", periods=4000, freq="5min", tz="UTC")
        c = 100 + np.cumsum(rng.normal(0, 0.1, len(idx)))
        self.bars = {"MNQ": pd.DataFrame({"open": c - 0.02, "high": c + 0.1, "low": c - 0.1, "close": c, "volume": 1}, index=idx)}


def test_build_run_report_full(tmp_path):
    grid = run_grid(run_fn, {"k": [1, 3, 5, 7, 9], "bias": [0.0, 0.0002]})
    wf = walk_forward(run_fn, {"k": [1, 5, 9]}, DAYS, 200, 60, purge=2)
    d = build_run_report(tmp_path / "run", RES, panel=FakePanel(), cfg={"robustness": {"bootstrap_n": 200, "mc_n": 200}},
                         run_fn=run_fn, extras={"grid": grid, "walkforward": wf})
    for f in ("metrics.json", "summary.md", "tearsheet.html", "robustness.json", "equity.parquet", "returns_daily.csv", "trades.csv",
              "grid_results.parquet", "walkforward.json", "env.json", "config.resolved.yaml"):
        assert (d / f).exists(), f
    assert (d / "tables" / "month.csv").exists()
    for f in ("metrics.json", "robustness.json", "walkforward.json"):
        json.loads((d / f).read_text(), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    rob = json.loads((d / "robustness.json").read_text())
    assert not rob.get("errors"), rob.get("errors")
    for k in ("psr", "bootstrap", "monte_carlo", "cost_sensitivity", "regimes", "grid", "pbo", "walkforward", "verdict"):
        assert k in rob, k
    assert rob["psr"]["dsr"] is not None and rob["psr"]["n_trials"] == 10
    s = (d / "summary.md").read_text()
    assert len(s.splitlines()) <= 110
    for h in ("# Run summary", "## Headline metrics", "## Robustness", "## Cost sensitivity", "## Warnings", "## Files"):
        assert h in s
    html = (d / "tearsheet.html").read_text()
    assert "plotly" in html.lower() and len(html) > 3_000_000        # plotly.js embedded
    assert not re.search(r"<script[^>]+src=", html)                  # nothing fetched at view time
    assert "section failed" not in html
    for sec in ("Equity", "Trade viewer", "Walk-forward", "Parameter grid", "Robustness"):
        assert sec in html
    assert html.count("candlestick") >= 5


def test_build_without_panel_runfn_trades(tmp_path):
    res = make_result(with_trades=False, with_bench=False, n_days=300)
    d = build_run_report(tmp_path / "r2", res)
    html = (d / "tearsheet.html").read_text()
    assert "Trade viewer" not in html and "section failed" not in html
    rob = json.loads((d / "robustness.json").read_text())
    assert "cost_sensitivity" not in rob and rob["verdict"]["overall"] in ("amber", "red", "green", "n/a")
    assert "no run_fn" in (d / "summary.md").read_text()


def test_custom_section_plugin(tmp_path):
    @register_section
    class Hello(Section):
        id, title, order = "hello", "Hello plug-in", 5

        def render(self, ctx):
            return "<p>plugin-ok</p>"

    try:
        d = build_run_report(tmp_path / "r3", make_result(n_days=200))
        assert "plugin-ok" in (d / "tearsheet.html").read_text()
    finally:
        SECTION_REGISTRY.pop("hello")


def test_run_dir_and_latest(tmp_path):
    from datetime import datetime
    d = make_run_dir(tmp_path, "sma cross", "abcdef123456", now=datetime(2026, 1, 2, 3, 4, 5))
    assert d.name == "20260102-030405_sma-cross_abcdef12"
    link = update_latest(d)
    assert link.is_symlink() and link.resolve() == d.resolve()


def test_compare(tmp_path):
    a = build_run_report(tmp_path / "a", make_result(seed=1, n_days=300), cfg={"robustness": {"bootstrap_n": 100}})
    b = build_run_report(tmp_path / "b", make_result(seed=2, n_days=300), cfg={"robustness": {"bootstrap_n": 100}})
    out = build_compare_report([a, b], tmp_path / "cmp")
    md = (out / "compare.md").read_text()
    assert md.count("\n| ") >= 3 and "Sharpe" in md
    assert "Growth of 1" in (out / "compare.html").read_text()


def test_intraday_result_smoke(tmp_path):
    from synth import SynthResult, make_trades
    rng = np.random.default_rng(4)
    days = pd.bdate_range("2024-01-02", periods=40)
    idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize("UTC") + pd.Timedelta(hours=14, minutes=30 + 5 * i) for d in days for i in range(78)])
    eq = pd.Series(1e5 + np.cumsum(rng.normal(2, 40, len(idx))), index=idx)
    daily = eq.groupby(eq.index.normalize()).last().pct_change().fillna(0.0)
    daily.index = pd.DatetimeIndex(days)
    res = SynthResult(eq, daily, pd.DataFrame({"MNQ": 1.0}, index=idx), make_trades(40), pd.Series(1.0, index=daily.index), None, None, 1e5,
                      {"strategy": "intra", "freq": "5m", "mode": "event", "seed": 1, "tz": "America/New_York"})
    d = build_run_report(tmp_path / "intra", res, panel=FakePanel(), cfg={"robustness": {"bootstrap_n": 100}})
    assert (d / "tables" / "hour_of_day.csv").exists()
    assert "section failed" not in (d / "tearsheet.html").read_text()
