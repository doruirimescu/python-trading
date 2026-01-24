from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from mrscore.core.results import Direction, EventStatus


@dataclass(frozen=True)
class Trade:
    job_id: str
    direction: Direction  # DOWN => short ratio (short num, long den), UP => long ratio
    status: EventStatus   # REVERTED / FAILED / EXPIRED

    entry_index: int
    exit_index: int
    duration: int

    entry_time: Optional[Any]
    exit_time: Optional[Any]

    entry_num: float
    entry_den: float
    exit_num: float
    exit_den: float

    qty_num: float  # signed quantity (short negative)
    qty_den: float

    gross_notional_entry: float
    gross_notional_exit: float

    pnl: float
    costs: float


@dataclass(frozen=True)
class EquityPoint:
    index: int
    time: Optional[Any]
    equity: float


@dataclass(frozen=True)
class BacktestResult:
    job_id: str
    initial_cash: float
    final_equity: float
    total_return: float

    trades: Optional[List[Trade]]
    equity_curve: Optional[List[EquityPoint]]
