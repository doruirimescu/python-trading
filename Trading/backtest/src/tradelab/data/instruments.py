"""Instrument specifications (tick size, point value, fees, session template)."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict


class InstrumentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = "EQUITY"
    kind: str = "equity"                  # future | equity
    tick_size: float = 0.0                # 0 => no rounding
    point_value: float = 1.0
    currency: str = "USD"
    commission_per_contract: float = 0.0  # per side
    exchange_fee_per_contract: float = 0.0  # per side
    tz: str = "America/New_York"
    session: str = "equity"               # equity | globex
    rth_start: str = "09:30"
    rth_end: str = "16:00"
    integer_qty: bool = True

    @property
    def fee_per_side(self) -> float:
        return self.commission_per_contract + self.exchange_fee_per_contract


_YAML = Path(__file__).with_name("instruments.yaml")


@lru_cache(maxsize=1)
def _registry() -> dict[str, dict[str, Any]]:
    with open(_YAML) as f:
        return yaml.safe_load(f)


def list_instruments() -> list[str]:
    return sorted(_registry())


def root_symbol(symbol: str) -> str:
    """'MNQ.v.0' -> 'MNQ'; 'MNQZ4' / 'MNQZ24' -> 'MNQ'; 'ES=F' -> 'ES'."""
    s = symbol.upper().split(".")[0].replace("=F", "")
    if s in _registry():
        return s
    m = re.match(r"^([A-Z]{1,3})[FGHJKMNQUVXZ]\d{1,2}$", s)
    if m and m.group(1) in _registry():
        return m.group(1)
    return s


def get_instrument(symbol: str, overrides: dict[str, Any] | None = None) -> InstrumentSpec:
    reg = _registry()
    root = root_symbol(symbol)
    base = dict(reg.get(root, reg["EQUITY"]))
    base["symbol"] = symbol
    if overrides:
        base.update(overrides)
    return InstrumentSpec(**base)
