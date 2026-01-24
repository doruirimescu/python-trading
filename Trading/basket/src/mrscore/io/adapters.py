from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Mapping, Optional, Sequence, Tuple

import numpy as np

from mrscore.io.history import History, OHLC


@dataclass(frozen=True)
class AlignedPanel:
    """
    Dense aligned panel for downstream basket/ratio computation.

    dates: shape (T,)
    symbols: length N
    values: shape (T, N) float64 (C-contiguous recommended)
    """
    dates: np.ndarray
    symbols: List[str]
    values: np.ndarray


# -----------------------------------------------------------------------------
# Validation helpers
# -----------------------------------------------------------------------------
def _ensure_sorted_dates(dates: np.ndarray, *, symbol: str) -> None:
    if dates.ndim != 1:
        raise ValueError(f"dates must be 1D for symbol {symbol}")
    if dates.size == 0:
        raise ValueError(f"empty dates for symbol {symbol}")
    # Dates must be non-decreasing; strictly increasing is ideal.
    if np.any(dates[1:] < dates[:-1]):
        raise ValueError(f"dates must be sorted ascending for symbol {symbol}")


def _as_float64_c_contig(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=np.float64, order="C")


# -----------------------------------------------------------------------------
# Alignment: intersection (strict)
# -----------------------------------------------------------------------------
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

    # Validate presence + sorted dates
    for s in symbols:
        if s not in histories:
            raise KeyError(f"Missing history for symbol '{s}'")
        _ensure_sorted_dates(histories[s].dates, symbol=s)

    # Start with dates from first symbol, intersect sequentially
    common = histories[symbols[0]].dates
    for s in symbols[1:]:
        common = np.intersect1d(common, histories[s].dates, assume_unique=False)

    if common.size == 0:
        raise ValueError("No intersecting dates across symbols")

    T = common.size
    N = len(symbols)
    mat = np.empty((T, N), dtype=np.float64)

    for j, s in enumerate(symbols):
        h = histories[s]
        x = h.field(field)
        idx = np.searchsorted(h.dates, common)
        # Verify exact matches
        if idx.size != common.size or np.any(idx < 0) or np.any(idx >= h.dates.size):
            raise ValueError(f"Failed to align dates for symbol {s}")
        if not np.array_equal(h.dates[idx], common):
            raise ValueError(f"Dates do not align exactly for symbol {s}")
        mat[:, j] = x[idx]

    return AlignedPanel(dates=common, symbols=list(symbols), values=_as_float64_c_contig(mat))


# -----------------------------------------------------------------------------
# Alignment: union (optional, tolerant)
# -----------------------------------------------------------------------------
def align_histories_union(
    histories: Dict[str, History],
    *,
    symbols: Sequence[str],
    field: OHLC,
    fill: Literal["none", "ffill"] = "none",
) -> AlignedPanel:
    """
    Align histories by the union of dates across all symbols.
    Missing values are NaN unless fill="ffill" is chosen.

    Use this only if you explicitly decide to tolerate missing dates.
    For strict statistical comparability, intersection is usually preferred.
    """
    if not symbols:
        raise ValueError("symbols must be non-empty")

    for s in symbols:
        if s not in histories:
            raise KeyError(f"Missing history for symbol '{s}'")
        _ensure_sorted_dates(histories[s].dates, symbol=s)

    # Union of all dates
    all_dates = histories[symbols[0]].dates
    for s in symbols[1:]:
        all_dates = np.union1d(all_dates, histories[s].dates)

    T = all_dates.size
    N = len(symbols)
    mat = np.full((T, N), np.nan, dtype=np.float64)

    for j, s in enumerate(symbols):
        h = histories[s]
        x = _as_float64_c_contig(h.field(field))
        idx = np.searchsorted(all_dates, h.dates)
        mat[idx, j] = x

        if fill == "ffill":
            _forward_fill_inplace(mat[:, j])

    return AlignedPanel(dates=all_dates, symbols=list(symbols), values=_as_float64_c_contig(mat))


def _forward_fill_inplace(col: np.ndarray) -> None:
    """
    Forward-fill NaNs in-place in a 1D float array.
    Leading NaNs remain NaN.
    """
    last = np.nan
    for i in range(col.size):
        v = col[i]
        if np.isnan(v):
            col[i] = last
        else:
            last = v


# -----------------------------------------------------------------------------
# Panel transforms (preprocessing, allowed to allocate)
# -----------------------------------------------------------------------------
def normalize_panel_by_first(
    panel: AlignedPanel,
    *,
    eps: float = 0.0,
) -> AlignedPanel:
    """
    Normalize each column by its first value:
      X[:, j] = X[:, j] / (X[0, j] + eps)

    eps is optional; use eps>0 only if you want to avoid divide-by-zero blowups.
    """
    X = _as_float64_c_contig(panel.values)
    base = X[0, :] + float(eps)
    if eps == 0.0 and np.any(base == 0.0):
        raise ValueError("Cannot normalize: one or more first values are zero")
    Xn = X / base
    return AlignedPanel(dates=panel.dates, symbols=panel.symbols, values=_as_float64_c_contig(Xn))


def compute_returns_from_prices(
    prices: np.ndarray,
    *,
    mode: Literal["log", "simple"] = "log",
) -> np.ndarray:
    """
    Compute returns from a 1D price series.
    Output length is len(prices)-1.

    - simple: r_t = (p_t / p_{t-1}) - 1
    - log:    r_t = log(p_t) - log(p_{t-1})

    NaNs propagate naturally.
    """
    p = _as_float64_c_contig(prices)
    if p.ndim != 1:
        raise ValueError("prices must be 1D")

    if mode == "simple":
        return (p[1:] / p[:-1]) - 1.0

    if mode == "log":
        return np.log(p[1:]) - np.log(p[:-1])

    raise ValueError(f"Invalid returns mode: {mode}")


def compute_panel_returns(
    panel: AlignedPanel,
    *,
    mode: Literal["log", "simple"] = "log",
) -> AlignedPanel:
    """
    Compute per-column returns from a price panel.
    Output has T-1 rows; dates are shifted to panel.dates[1:].
    """
    X = _as_float64_c_contig(panel.values)
    if X.ndim != 2:
        raise ValueError("panel.values must be 2D")

    if mode == "simple":
        R = (X[1:, :] / X[:-1, :]) - 1.0
    elif mode == "log":
        R = np.log(X[1:, :]) - np.log(X[:-1, :])
    else:
        raise ValueError(f"Invalid returns mode: {mode}")

    return AlignedPanel(dates=panel.dates[1:], symbols=panel.symbols, values=_as_float64_c_contig(R))


# -----------------------------------------------------------------------------
# Convenience: Build panel from histories + optionally normalize
# -----------------------------------------------------------------------------
def build_price_panel(
    histories: Mapping[str, History],
    *,
    symbols: Sequence[str],
    field: OHLC,
    align: Literal["intersection", "union"] = "intersection",
    normalize_by_first: bool = True,
    union_fill: Literal["none", "ffill"] = "none",
) -> AlignedPanel:
    """
    One-stop helper:
    - Align histories (intersection or union)
    - Optionally normalize columns by first value

    Note: this is preprocessing. Use once per symbol set.
    """
    if align == "intersection":
        panel = align_histories_intersection(dict(histories), symbols=symbols, field=field)
    elif align == "union":
        panel = align_histories_union(dict(histories), symbols=symbols, field=field, fill=union_fill)
    else:
        raise ValueError(f"Invalid align mode: {align}")

    if normalize_by_first:
        panel = normalize_panel_by_first(panel)

    return panel
