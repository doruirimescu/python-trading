from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np

from mrscore.io.history import History, OHLC


@dataclass(frozen=True)
class AlignedPanel:
    dates: np.ndarray              # shape (T,)
    symbols: List[str]             # length N
    values: np.ndarray             # shape (T, N), float64


def align_histories_intersection(
    histories: Dict[str, History],
    *,
    symbols: Sequence[str],
    field: OHLC,
) -> AlignedPanel:
    """
    Align histories by the intersection of dates across all symbols.
    Produces a dense (T, N) float64 matrix for downstream ratio/basket ops.

    This is preprocessing: it may allocate; it must not run inside the hot loop.
    """
    if not symbols:
        raise ValueError("symbols must be non-empty")

    # Start with dates from first symbol, intersect sequentially (fast set-like on sorted arrays)
    base_dates = histories[symbols[0]].dates
    common = base_dates
    for s in symbols[1:]:
        common = np.intersect1d(common, histories[s].dates, assume_unique=False)

    if common.size == 0:
        raise ValueError("No intersecting dates across symbols")

    # Build aligned matrix
    T = common.size
    N = len(symbols)
    mat = np.empty((T, N), dtype=np.float64)

    for j, s in enumerate(symbols):
        h = histories[s]
        x = h.field(field)
        # map common dates into each history via searchsorted
        idx = np.searchsorted(h.dates, common)
        # Validate exact match (searchsorted assumes sorted)
        if not np.array_equal(h.dates[idx], common):
            raise ValueError(f"Dates not strictly sortable/aligned for symbol {s}")
        mat[:, j] = x[idx]

    return AlignedPanel(dates=common, symbols=list(symbols), values=mat)
