import json

import numpy as np
import pandas as pd
import pytest

from tradelab.cli import main
from tradelab.config import load_config
from tradelab.engine import TRADE_COLUMNS, basic_metrics, config_hash, make_run_fn, run_backtest


@pytest.mark.parametrize("cfgfile,min_trades", [("example_daily", 3), ("example_mnq_intraday", 20)])
def test_cli_run_writes_full_run_dir(cfgfile, min_trades, tmp_path):
    rc = main(["run", f"experiments/{cfgfile}.yaml", "--out-dir", str(tmp_path)])
    assert rc == 0
    d = (tmp_path / "LATEST").resolve()
    for f in ("config.resolved.yaml", "equity.parquet", "returns_daily.csv", "trades.csv", "data_quality.json", "env.json", "metrics.json",
              "causality.json", "summary.md", "tearsheet.html", "robustness.json", "walkforward.json", "grid_results.parquet"):
        assert (d / f).exists(), f
    m = json.loads((d / "metrics.json").read_text())
    assert m["trades"]["n_trades"] >= min_trades and np.isfinite(m["max_drawdown"])
    assert json.loads((d / "causality.json").read_text())["ok"] is True
    assert "section failed" not in (d / "tearsheet.html").read_text()
    assert "errors" not in json.loads((d / "robustness.json").read_text())
    tr = pd.read_csv(d / "trades.csv")
    assert list(tr.columns) == TRADE_COLUMNS
    env = json.loads((d / "env.json").read_text())
    assert {"python", "pandas", "config_hash", "seed"} <= set(env)


def test_determinism_same_config_same_hash_and_results():
    cfg = load_config("experiments/example_mnq_intraday.yaml")
    r1, _, _ = run_backtest(cfg)
    r2, _, _ = run_backtest(load_config("experiments/example_mnq_intraday.yaml"))
    assert config_hash(cfg) == config_hash(load_config("experiments/example_mnq_intraday.yaml"))
    pd.testing.assert_series_equal(r1.equity, r2.equity)
    pd.testing.assert_frame_equal(r1.trades, r2.trades)
    assert r1.meta["data_fingerprint"] == r2.meta["data_fingerprint"]
    assert r1.meta["config_hash"] == r2.meta["config_hash"] and r1.meta["strategy"] == "orb_intraday"


def test_make_run_fn_params_costs_and_slicing():
    cfg = load_config("experiments/example_daily.yaml")
    run_fn = make_run_fn(cfg)
    base = run_fn({})
    wide = run_fn({"fast": 10, "slow": 50})
    assert base.meta["params"]["fast"] == 20 and wide.meta["params"]["fast"] == 10
    assert not np.allclose(base.equity.to_numpy(), wide.equity.to_numpy())
    c0, c3 = run_fn({}, cost_mult=0.0), run_fn({}, cost_mult=3.0)
    assert c0.equity.iloc[-1] > base.equity.iloc[-1] > c3.equity.iloc[-1]
    assert c0.costs_daily.sum() == 0
    sl = run_fn({}, start="2010-01-01", end="2014-12-31")
    assert sl.returns_daily.index.min() >= pd.Timestamp("2010-01-01") and sl.returns_daily.index.max() <= pd.Timestamp("2014-12-31")
    assert sl.initial_capital == cfg.initial_capital
    assert isinstance(basic_metrics(base)["sharpe"], float)


def test_cli_misc_commands(capsys, tmp_path):
    assert main(["list-strategies"]) == 0 and "sma_cross" in capsys.readouterr().out
    assert main(["list-sources"]) == 0 and "databento" in capsys.readouterr().out
    assert main(["describe", "orb_intraday"]) == 0 and "or_minutes" in capsys.readouterr().out
    assert main(["validate-data", "experiments/example_mnq_intraday.yaml"]) == 0
