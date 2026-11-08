import pytest
import numpy as np
import pandas as pd
from leaky_strats import (LeakyEventFutureFeature, LeakyEventLateStash, LeakyEventSessionAggregate,
                          LeakyEventShiftedBack, LeakyEventStashedBenchmark, LeakyEventStashedCash,
                          LeakyEventStashedPanel, LeakyVecFuture, LeakyVecGlobalStat)

from tradelab.config import DataCfg, ExecCfg, RiskRules
from tradelab.data import load_panel
from tradelab.engine import check_causality, engine_delay_check
from tradelab.strategy import list_strategies


@pytest.fixture(scope="module")
def daily():
    return load_panel(DataCfg(source="synthetic", symbols=["SPY"], freq="1d", start="2019-01-01", end="2021-12-31"))


@pytest.fixture(scope="module")
def intraday():
    return load_panel(DataCfg(source="synthetic", symbols=["MNQ"], freq="5m", base_freq="1m", start="2023-03-01", end="2023-04-14", options={"seed": 3, "bid_ask": True}))


EX_D = ExecCfg()
EX_I = ExecCfg(flatten_at="15:55", slippage_ticks=1, risk=RiskRules(trade_window=("10:00", "15:00"), max_trades_per_day=1))


@pytest.mark.parametrize("name", sorted(list_strategies()))
def test_all_registered_strategies_are_causal(name, daily, intraday):
    cls = list_strategies()[name]
    panel, ex = (daily, EX_D) if cls.mode == "vector" else (intraday, EX_I)
    rep = check_causality(lambda: cls(cls.Params()), panel, ex)
    assert rep.ok, rep.summary()
    assert len(rep.checks) >= 4


@pytest.mark.parametrize("cls,mode", [
    (LeakyVecFuture, "d"), (LeakyVecGlobalStat, "d"),
    (LeakyEventFutureFeature, "i"), (LeakyEventSessionAggregate, "i"), (LeakyEventShiftedBack, "i"),
    (LeakyEventStashedPanel, "i"),
])
def test_deliberately_leaky_strategies_are_caught(cls, mode, daily, intraday):
    panel, ex = (daily, EX_D) if mode == "d" else (intraday, EX_I)
    rep = check_causality(lambda: cls(cls.Params()), panel, ex)
    assert not rep.ok, f"{cls.__name__} was NOT caught\n{rep.summary()}"
    assert any(not c["ok"] for c in rep.checks)


def test_future_poison_alone_catches_last_bar_peek(intraday):
    rep = check_causality(lambda: LeakyEventShiftedBack(LeakyEventShiftedBack.Params()), intraday, EX_I)
    # prefix runs differ because the 'last bar' differs between prefixes
    assert any(c["name"].startswith("prefix_invariance") and not c["ok"] for c in rep.checks)
    assert any(c["name"].startswith("future_poison") and not c["ok"] for c in rep.checks)


def test_engine_delay_oracle_sanity(daily):
    long = load_panel(DataCfg(source="synthetic", symbols=["SPY"], freq="1d", start="2005-01-01", end="2024-12-31"))
    d = engine_delay_check(long)
    assert d["ok"], d
    assert d["sharpe_unsafe"] > 5 and abs(d["sharpe_next_close"]) < 1.5


def test_cli_check_causality_exit_codes(tmp_path):
    import yaml
    from tradelab.cli import main
    assert main(["check-causality", "experiments/example_daily.yaml"]) == 0
    cfg = yaml.safe_load(open("experiments/example_daily.yaml"))
    cfg["strategy"] = {"name": "leaky_strats:LeakyVecFuture", "params": {}}
    cfg["data"]["start"], cfg["data"]["end"] = "2012-01-01", "2021-12-31"
    p = tmp_path / "leaky.yaml"
    p.write_text(yaml.safe_dump(cfg))
    assert main(["check-causality", str(p), "--skip-engine"]) == 4


def test_stashed_panel_on_bar_lookahead_is_caught_by_order_log(intraday):
    """Finding 5: features look causal, but on_bar reads c[i+1] from a panel stashed in prepare()."""
    rep = check_causality(lambda: LeakyEventStashedPanel(LeakyEventStashedPanel.Params()), intraday, EX_I)
    assert not rep.ok, rep.summary()
    failed = [c["name"] for c in rep.checks if not c["ok"]]
    assert failed and all(n.startswith("orders_prefix") for n in failed), rep.summary()   # features + trades pass


def test_cuts_are_sampled_across_the_whole_dataset_not_only_the_first_bars(intraday):
    n = len(intraday.index)
    mk = lambda: LeakyEventLateStash(LeakyEventLateStash.Params())     # clean before 2023-04-03
    rep = check_causality(mk, intraday, EX_I, max_bars=n // 3)         # old harness only looked at the first max_bars
    assert not rep.ok, rep.summary()
    cuts = sorted({int(c["name"].split("@")[1]) for c in rep.checks})
    assert cuts[-1] > n // 2 and len(cuts) >= 2


def _with_macro(panel):
    import dataclasses
    days = pd.DatetimeIndex(sorted(panel[panel.primary]["session_date"].unique()))
    rng = np.random.default_rng(0)
    p = dataclasses.replace(panel)
    p.benchmark = pd.Series(rng.normal(0, 0.01, len(days)), index=days)
    p.cash = pd.Series(0.00005, index=days)
    return p


def test_cash_and_benchmark_are_poisoned_too(intraday):
    p = _with_macro(intraday)
    for cls in (LeakyEventStashedBenchmark, LeakyEventStashedCash):
        rep = check_causality(lambda cls=cls: cls(cls.Params()), p, EX_I)
        assert not rep.ok, f"{cls.__name__} NOT caught\n{rep.summary()}"


def test_poison_panel_keeps_past_macro_series_and_replaces_future(intraday):
    from tradelab.engine import poison_panel
    p = _with_macro(intraday)
    T = len(p.index) // 2
    q = poison_panel(p, T)
    d_cut = pd.Timestamp(p["MNQ"]["session_date"].iloc[T])
    past = p.benchmark.index < d_cut
    assert np.array_equal(q.benchmark[past].to_numpy(), p.benchmark[past].to_numpy())
    assert not np.allclose(q.benchmark[~past].to_numpy(), p.benchmark[~past].to_numpy())
    assert (q.cash != p.cash).any() and (q.cash.index[q.cash != p.cash] > pd.Timestamp(p["MNQ"]["session_date"].iloc[T - 1])).all()


def test_engine_delay_oracle_on_intraday_costly_instrument():
    """Regression: the oracle used to inherit MNQ's commission; flipping every bar made next_close Sharpe -2.2 (FAIL)."""
    panel = load_panel(DataCfg(source="synthetic", symbols=["MNQ"], freq="5m", base_freq="1m", start="2022-01-03",
                               end="2023-12-29", options={"seed": 11, "bid_ask": True}))
    d = engine_delay_check(panel.head(8000))
    assert d["ok"], d
    assert abs(d["sharpe_next_close"]) < 1.0 and d["sharpe_unsafe"] > 20


@pytest.mark.parametrize("name", sorted(list_strategies()))
def test_legitimate_strategies_still_pass_with_cash_and_benchmark_poisoned(name, daily, intraday):
    cls = list_strategies()[name]
    panel, ex = (daily, EX_D) if cls.mode == "vector" else (intraday, EX_I)
    rep = check_causality(lambda: cls(cls.Params()), _with_macro(panel), ex)
    assert rep.ok, rep.summary()
