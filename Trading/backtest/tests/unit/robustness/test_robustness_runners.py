import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "golden"))
from synth import TRADE_COLS, result_from_returns  # noqa: E402

from tradelab.robustness import cost_sensitivity, make_folds, run_grid, walk_forward  # noqa: E402
from tradelab.robustness.grid import expand_grid, heatmap_data  # noqa: E402

DAYS = pd.bdate_range("2020-01-01", periods=1200)
NOISE = pd.Series(np.random.default_rng(0).normal(0, 0.01, len(DAYS)), index=DAYS)


def fake_run(params, *, start=None, end=None, cost_mult=1.0):
    """Edge peaks at k=5 (smoothly); costs 0.0005/day*mult*|k-based turnover|."""
    k = params.get("k", 5)
    edge = 0.0015 * max(0.0, 1 - abs(k - 5) / 5) + params.get("bias", 0.0)
    r = NOISE + edge - 0.0003 * cost_mult
    if start is not None:
        r = r[r.index >= pd.Timestamp(start)]
    if end is not None:
        r = r[r.index <= pd.Timestamp(end)]
    tr = pd.DataFrame({c: [] for c in TRADE_COLS})
    tr = pd.DataFrame([{**{c: 0 for c in TRADE_COLS}, "net_pnl": float(v) * 1e5} for v in r.iloc[:30]])
    return result_from_returns(r, trades=tr)


def test_expand_and_grid_best_and_plateau():
    g = {"k": [1, 3, 5, 7, 9]}
    assert len(expand_grid({"a": [1, 2], "b": [3, 4, 5]})) == 6
    gr = run_grid(fake_run, g, "sharpe", seed=1)
    assert gr.best_params == {"k": 5} and gr.n_trials == 5
    assert gr.returns_matrix.shape == (len(DAYS), 5)
    assert 0 < gr.plateau_score <= 1
    gr2 = run_grid(fake_run, {"k": [1, 3, 5, 7, 9], "bias": [0.0, 0.0005]}, "total_return")
    assert gr2.best_params == {"k": 5, "bias": 0.0005}
    hm = heatmap_data(gr2.table, "k", "bias")
    assert hm.shape == (2, 5)


def test_grid_random_reproducible():
    g = {"k": list(range(1, 10)), "bias": [0.0, 0.0001, 0.0002]}
    a = expand_grid(g, "random", 7, seed=3)
    assert a == expand_grid(g, "random", 7, seed=3) and len(a) == 7


def test_make_folds_nonoverlapping_with_purge():
    folds = make_folds(1000, is_len=300, oos_len=100, purge=5)
    assert len(folds) == 6
    for f in folds:
        assert f["oos_start"] - f["is_end"] == 5
    for a, b in zip(folds, folds[1:]):
        assert a["oos_end"] <= b["oos_start"]          # OOS windows do not overlap
    anch = make_folds(1000, 300, 100, scheme="anchored", purge=2)
    assert all(f["is_start"] == 0 for f in anch)
    assert anch[1]["is_end"] == 400
    for a, b in zip(anch, anch[1:]):
        assert a["oos_end"] <= b["oos_start"]
    assert all(f["oos_end"] <= 1000 for f in folds + anch)


def test_walk_forward_end_to_end():
    wf = walk_forward(fake_run, {"k": [1, 5, 9]}, DAYS, is_len=300, oos_len=100, purge=3, initial_capital=1e5)
    d = wf.to_dict()
    assert d["n_folds"] == 8
    assert all(f["params"] == {"k": 5} for f in wf.folds)
    # stitched OOS covers exactly the union of OOS windows, no duplicate dates
    assert wf.oos_returns.index.is_unique and len(wf.oos_returns) == 8 * 100
    for f in wf.folds:
        assert pd.Timestamp(f["is_end_date"]) < pd.Timestamp(f["oos_start_date"])
    assert np.isfinite(wf.efficiency)
    assert wf.oos_equity.iloc[0] > 0


def test_cost_sensitivity():
    out = cost_sensitivity(fake_run, {"k": 5}, mults=(0, 1, 2, 3), variants={"bias+": {"bias": 0.001}})
    t = out["table"]
    assert list(t["label"]) == ["0x", "1x", "2x", "3x", "bias+"]
    assert t.loc[0, "total_return"] > t.loc[1, "total_return"] > t.loc[3, "total_return"]
    assert out["positive_at_2x"] in (True, False)
    # (sample mean + edge 0.0015/day) / cost 0.0003/day  (compounding makes it approximate)
    assert out["breakeven_cost_mult"] == pytest.approx((NOISE.mean() + 0.0015 - NOISE.var() / 2) / 0.0003, rel=0.1)
