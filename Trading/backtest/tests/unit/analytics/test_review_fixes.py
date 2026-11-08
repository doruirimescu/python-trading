"""Regression tests for the correctness review (analytics / optimiser objective)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "golden"))
from synth import make_result, result_from_returns  # noqa: E402

from tradelab.analytics import compute_metrics  # noqa: E402
from tradelab.robustness.grid import score_result  # noqa: E402


def test_cagr_uses_calendar_span_not_row_count():
    # one year of calendar time but only 100 observations (sparse sample): 252-row convention would say 0.4 years
    idx = pd.DatetimeIndex(pd.date_range("2023-01-02", "2023-12-29", periods=100).normalize().unique())
    r = pd.Series(0.001 + 1e-4 * np.sin(np.arange(len(idx))), index=idx)
    m = compute_metrics(result_from_returns(r), periods_per_year=252)
    years = ((idx[-1] - idx[0]).days + 1) / 365.25
    total = float((1 + r).prod() - 1)
    assert m["cagr"] == pytest.approx((1 + total) ** (1 / years) - 1)
    # a full business-day year gives CAGR ~ total return
    bd = pd.bdate_range("2023-01-02", "2023-12-29")
    full = pd.Series(0.0004 + 1e-4 * np.sin(np.arange(len(bd))), index=bd)
    mf = compute_metrics(result_from_returns(full), periods_per_year=252)
    assert mf["cagr"] == pytest.approx(mf["total_return"], rel=0.02)


def test_grid_objective_matches_reported_sharpe_with_rf():
    res = make_result(n_days=300)                 # rf_daily = 5e-5 / day
    assert res.rf_daily is not None
    m = compute_metrics(res, periods_per_year=252)
    assert score_result(res, "sharpe", 252) == pytest.approx(m["sharpe"])
    assert score_result(res, "sortino", 252) == pytest.approx(m["sortino"])
    no_rf = make_result(n_days=300)
    object.__setattr__(no_rf, "rf_daily", None)
    assert score_result(no_rf, "sharpe", 252) != pytest.approx(m["sharpe"])
