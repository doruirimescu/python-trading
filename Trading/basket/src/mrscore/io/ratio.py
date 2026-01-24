from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from mrscore.io.adapters import AlignedPanel


@dataclass(frozen=True)
class BasketSpec:
    """Linear basket: sum(weights_i * s_i)."""
    indices: np.ndarray            # int32/64 indices into panel columns
    weights: np.ndarray            # float64 weights, same length as indices

    def __post_init__(self) -> None:
        if self.indices.ndim != 1 or self.weights.ndim != 1:
            raise ValueError("indices and weights must be 1D")
        if self.indices.size == 0:
            raise ValueError("basket cannot be empty")
        if self.indices.size != self.weights.size:
            raise ValueError("indices and weights must have same length")


@dataclass(frozen=True)
class RatioSpec:
    numerator: BasketSpec
    denominator: BasketSpec
    eps: float = 1e-12


def build_equal_weight_basket(indices: Sequence[int]) -> BasketSpec:
    idx = np.asarray(indices, dtype=np.int64)
    w = np.ones(idx.size, dtype=np.float64)
    return BasketSpec(indices=idx, weights=w)


def compute_basket_series(panel: AlignedPanel, basket: BasketSpec) -> np.ndarray:
    """
    Vectorized basket series: y_t = sum_i w_i * x_{t, idx_i}
    """
    # (T, k) take -> (T, k) * (k,) -> sum axis=1
    X = panel.values[:, basket.indices]
    return (X * basket.weights).sum(axis=1)


def compute_ratio_series(panel: AlignedPanel, spec: RatioSpec) -> np.ndarray:
    num = compute_basket_series(panel, spec.numerator)
    den = compute_basket_series(panel, spec.denominator)
    return num / (den + spec.eps)
