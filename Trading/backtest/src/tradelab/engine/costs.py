"""Cost model: commissions (per contract/side + bps), slippage (ticks + bps), stop surcharge."""
from __future__ import annotations

from dataclasses import dataclass

from ..config.schema import ExecCfg
from ..data.instruments import InstrumentSpec


@dataclass(frozen=True)
class CostModel:
    fee_per_side: float            # $ per contract per side (commission + exchange), total
    commission_bps: float
    slip_ticks: float
    slip_bps: float
    stop_extra_ticks: float
    tick: float
    pv: float

    @classmethod
    def from_cfg(cls, ex: ExecCfg, spec: InstrumentSpec, mult: float = 1.0) -> "CostModel":
        fee = ex.commission_per_contract if ex.commission_per_contract is not None else spec.fee_per_side
        return cls(fee * mult, ex.commission_bps * mult, ex.slippage_ticks * mult, ex.slippage_bps * mult,
                   ex.stop_extra_slippage_ticks * mult, spec.tick_size, spec.point_value)

    def commission(self, qty: float, px: float) -> float:
        return abs(qty) * self.fee_per_side + abs(qty) * px * self.pv * self.commission_bps / 1e4

    def slippage(self, qty: float, px: float, is_stop: bool = False) -> float:
        """$ cost of adverse slippage on one fill."""
        ticks = self.slip_ticks + (self.stop_extra_ticks if is_stop else 0.0)
        pts = ticks * self.tick + px * self.slip_bps / 1e4
        return abs(qty) * pts * self.pv
