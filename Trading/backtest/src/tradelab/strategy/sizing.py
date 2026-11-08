"""Position-sizing helpers (pure functions)."""
from __future__ import annotations

import math


def fixed_fraction(equity: float, fraction: float, price: float, point_value: float = 1.0, integer: bool = True) -> float:
    q = equity * fraction / (price * point_value)
    return float(math.floor(q)) if integer else q


def fixed_contracts(n: float) -> float:
    return float(n)


def vol_target(equity: float, target_vol: float, asset_vol: float, price: float, point_value: float = 1.0, integer: bool = True) -> float:
    """Contracts so that annualised $ vol of the position ~= target_vol * equity. asset_vol is annualised return vol."""
    if asset_vol <= 0 or price <= 0:
        return 0.0
    q = target_vol * equity / (asset_vol * price * point_value)
    return float(math.floor(q)) if integer else q


def risk_based(equity: float, risk_pct: float, stop_distance_pts: float, point_value: float, integer: bool = True) -> float:
    """floor(risk$ / (stop_pts * point_value))."""
    if stop_distance_pts <= 0:
        return 0.0
    q = equity * risk_pct / (stop_distance_pts * point_value)
    return float(math.floor(q)) if integer else q
