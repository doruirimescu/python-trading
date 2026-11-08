import pytest
from pydantic import ValidationError

from tradelab.config import RunConfig, load_config
from tradelab.strategy import Order, Strategy, get_strategy, grid_axes, list_strategies, sizing


def test_registry_discovers_examples():
    names = list_strategies()
    assert {"sma_cross", "orb_intraday"} <= set(names)
    assert names["sma_cross"].mode == "vector" and names["orb_intraday"].mode == "event"
    assert get_strategy("sma_cross") is names["sma_cross"]
    with pytest.raises(KeyError):
        get_strategy("does_not_exist")


def test_module_class_spec():
    cls = get_strategy("tradelab.engine.causality:_Foresight")
    assert issubclass(cls, Strategy)


def test_params_extra_forbid_and_grid_axes():
    cls = get_strategy("sma_cross")
    with pytest.raises(ValidationError):
        cls.Params(fast=5, bogus=1)
    ax = grid_axes(cls.Params)
    assert ax["fast"][0] == 5 and ax["fast"][-1] == 50 and ax["slow"] == [60, 80, 100, 120, 140, 160, 180, 200]
    assert "long_only" not in ax
    assert grid_axes(get_strategy("orb_intraday").Params)["or_minutes"] == [15, 30, 60]


def test_order_helpers():
    o = Order("sell", qty=1)
    assert o.sign == -1 and Order.flatten().kind == "flatten" and Order.modify(stop=1.0).stop == 1.0


def test_sizing_helpers():
    assert sizing.risk_based(100_000, 0.01, 2.5, 2.0) == 200
    assert sizing.fixed_fraction(100_000, 0.5, 4000, 2.0) == 6
    assert sizing.vol_target(100_000, 0.1, 0.2, 100, 1.0) == 500
    assert sizing.fixed_contracts(3) == 3.0


def test_config_forbids_extra_and_loads_examples():
    with pytest.raises(ValidationError):
        RunConfig.model_validate({"data": {"symbols": ["A"]}, "strategy": {"name": "x"}, "oops": 1})
    for f in ("example_daily", "example_mnq_intraday"):
        cfg = load_config(f"experiments/{f}.yaml")
        assert cfg.config_version == 1
