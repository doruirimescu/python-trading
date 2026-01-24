from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import numpy as np

from mrscore.utils.logging import get_logger


logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Minimal dependency: a pre-aligned dense price panel (T, N).
# Put the canonical definition in mrscore/io/adapters.py; this is a structural type.
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class AlignedPanel:
    dates: np.ndarray              # shape (T,)
    symbols: List[str]             # length N
    values: np.ndarray             # shape (T, N), float64 recommended


# -----------------------------------------------------------------------------
# Basket library: caches all k-combinations of column indices.
# Storing baskets (size C(N,k) * k) is often acceptable; storing ratios is not.
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class BasketLibrary:
    k: int
    baskets: np.ndarray  # shape (B, k), dtype int32/int64

    def __post_init__(self) -> None:
        if self.baskets.ndim != 2 or self.baskets.shape[1] != self.k:
            raise ValueError("baskets must be shaped (B, k)")

    @property
    def size(self) -> int:
        return int(self.baskets.shape[0])


@dataclass(frozen=True)
class RatioJob:
    """
    Lightweight handle for a ratio = basket(num_id) / basket(den_id).

    Note: we keep only integer IDs; the libraries hold the actual index arrays.
    """
    k_num: int
    k_den: int
    num_id: int
    den_id: int


# -----------------------------------------------------------------------------
# RatioUniverse
# -----------------------------------------------------------------------------
class RatioUniverse:
    """
    Generates and evaluates basket ratios over a pre-aligned price panel.

    Key performance principle:
    - We may cache basket combinations (C(N,k) items).
    - We must not cache ratios (O(C(N,k)^2) items).
    """

    def __init__(
        self,
        panel: AlignedPanel,
        *,
        normalize_by_first: bool = True,
        eps: float = 1e-12,
        dtype: np.dtype = np.float64,
    ) -> None:
        if panel.values.ndim != 2:
            raise ValueError("panel.values must be 2D (T, N)")
        if panel.values.shape[1] != len(panel.symbols):
            raise ValueError("panel.values columns must match len(panel.symbols)")
        if panel.values.shape[0] != len(panel.dates):
            raise ValueError("panel.values rows must match len(panel.dates)")

        logger.info(
            "Initializing RatioUniverse: T=%d N=%d normalize_by_first=%s eps=%s dtype=%s",
            panel.values.shape[0],
            panel.values.shape[1],
            normalize_by_first,
            eps,
            dtype,
        )

        self.dates = panel.dates
        self.symbols = panel.symbols
        self._eps = float(eps)

        # Ensure float64 contiguous matrix for downstream speed.
        X = np.asarray(panel.values, dtype=dtype, order="C")

        # Optional: normalize each symbol by first value (vectorized).
        if normalize_by_first:
            base = X[0, :]
            # Avoid division-by-zero blowups; you can choose a stricter policy later.
            base_safe = np.where(base == 0.0, 1.0, base)
            X = X / base_safe
            logger.info("Normalized panel by first value (vectorized)")

        self._X = X  # shape (T, N)
        self._N = X.shape[1]

        # Basket libraries keyed by k
        self._basket_libs: Dict[int, BasketLibrary] = {}

        # Map symbol -> column index (useful if you later accept symbol specs)
        self._sym2idx = {s: i for i, s in enumerate(self.symbols)}

    # ----------------------------
    # Public helpers
    # ----------------------------
    def symbol_to_index(self, symbol: str) -> int:
        return self._sym2idx[symbol]

    def estimate_ratio_count(
        self,
        *,
        k_num: int,
        k_den: int,
        unordered_if_equal_k: bool = True,
        disallow_overlap: bool = False,  # overlap filtering makes exact counting harder
    ) -> int:
        """
        Estimate number of ratio jobs.

        - If k_num == k_den and unordered_if_equal_k=True:
            count = C(C(N,k), 2)   (matches legacy 'combinations of combinations' semantics)
        - Else:
            count = C(N,k_num) * C(N,k_den)  (ordered pairs)

        If disallow_overlap=True, this is an upper bound (we do not compute exact count).
        """
        N = self._N
        if k_num < 1 or k_den < 1:
            raise ValueError("k_num and k_den must be >= 1")
        if k_num > N or k_den > N:
            return 0

        b_num = comb(N, k_num)
        b_den = comb(N, k_den)

        if k_num == k_den and unordered_if_equal_k:
            # choose 2 baskets out of b_num
            total = comb(b_num, 2) if b_num >= 2 else 0
        else:
            total = b_num * b_den

        # Overlap filtering reduces count; return upper bound
        return int(total)

    # ----------------------------
    # Basket library building
    # ----------------------------
    def get_basket_library(self, k: int) -> BasketLibrary:
        """
        Caches all k-combinations of column indices.
        """
        if k in self._basket_libs:
            return self._basket_libs[k]
        if k < 1:
            raise ValueError("k must be >= 1")
        if k > self._N:
            raise ValueError(f"k={k} exceeds number of symbols N={self._N}")

        # Generate all k-combinations of indices 0..N-1
        # This materializes C(N,k) baskets (acceptable); DO NOT materialize ratios.
        baskets = np.array(list(combinations(range(self._N), k)), dtype=np.int32)
        lib = BasketLibrary(k=k, baskets=baskets)
        self._basket_libs[k] = lib
        logger.info("Built basket library for k=%d size=%d", k, lib.size)
        return lib

    # ----------------------------
    # Job iteration
    # ----------------------------
    def iter_ratio_jobs(
        self,
        *,
        k_num: int,
        k_den: int,
        unordered_if_equal_k: bool = True,
        disallow_overlap: bool = False,
        max_jobs: Optional[int] = None,
    ) -> Iterator[RatioJob]:
        """
        Generate RatioJob objects without materializing all ratios.

        - If k_num == k_den and unordered_if_equal_k=True:
            yields (i, j) with i < j over the same basket library (unordered pair).
        - Else:
            yields ordered pairs (i, j) across two libraries.

        disallow_overlap:
            skips jobs where numerator and denominator baskets share any symbol.
        """
        if max_jobs is not None and max_jobs < 0:
            raise ValueError("max_jobs must be >= 0")

        lib_num = self.get_basket_library(k_num)
        lib_den = lib_num if (k_num == k_den) else self.get_basket_library(k_den)

        logger.info(
            "Iterating ratio jobs: k_num=%d k_den=%d unordered_if_equal_k=%s disallow_overlap=%s max_jobs=%s",
            k_num,
            k_den,
            unordered_if_equal_k,
            disallow_overlap,
            max_jobs,
        )

        produced = 0

        if k_num == k_den and unordered_if_equal_k:
            # Unordered pairs of baskets: i < j
            for i in range(lib_num.size - 1):
                bi = lib_num.baskets[i]
                for j in range(i + 1, lib_num.size):
                    bj = lib_num.baskets[j]
                    if disallow_overlap and _has_overlap_sorted_ints(bi, bj):
                        continue

                    yield RatioJob(k_num=k_num, k_den=k_den, num_id=i, den_id=j)
                    produced += 1
                    if max_jobs is not None and produced >= max_jobs:
                        return
        else:
            # Ordered pairs across potentially different libs
            for i in range(lib_num.size):
                bi = lib_num.baskets[i]
                for j in range(lib_den.size):
                    bj = lib_den.baskets[j]
                    if disallow_overlap and _has_overlap_sorted_ints(bi, bj):
                        continue

                    yield RatioJob(k_num=k_num, k_den=k_den, num_id=i, den_id=j)
                    produced += 1
                    if max_jobs is not None and produced >= max_jobs:
                        return

    # ----------------------------
    # Compute series for a job
    # ----------------------------
    def compute_ratio_series(self, job: RatioJob) -> np.ndarray:
        """
        Compute ratio series y_t for a RatioJob:
            y_t = sum(X[t, num_idx]) / (sum(X[t, den_idx]) + eps)

        Returns a new float64 array of shape (T,).
        """
        lib_num = self.get_basket_library(job.k_num)
        lib_den = lib_num if job.k_num == job.k_den else self.get_basket_library(job.k_den)

        num_idx = lib_num.baskets[job.num_id]
        den_idx = lib_den.baskets[job.den_id]

        num = self._X[:, num_idx].sum(axis=1)
        den = self._X[:, den_idx].sum(axis=1)
        return num / (den + self._eps)

    def compute_ratio_series_into(self, out: np.ndarray, job: RatioJob) -> None:
        """
        Compute ratio series into a preallocated array `out` of shape (T,).

        This reduces allocations when scanning many ratios.
        """
        if out.shape != (self._X.shape[0],):
            raise ValueError(f"out must have shape ({self._X.shape[0]},)")

        lib_num = self.get_basket_library(job.k_num)
        lib_den = lib_num if job.k_num == job.k_den else self.get_basket_library(job.k_den)

        num_idx = lib_num.baskets[job.num_id]
        den_idx = lib_den.baskets[job.den_id]

        np.sum(self._X[:, num_idx], axis=1, out=out)
        den = self._X[:, den_idx].sum(axis=1)
        out /= (den + self._eps)

    # ----------------------------
    # Scan interface (replaces legacy RatioGenerator pattern)
    # ----------------------------
    def scan(
        self,
        *,
        k_num: int,
        k_den: int,
        process: Callable[[RatioJob, np.ndarray], bool],
        unordered_if_equal_k: bool = True,
        disallow_overlap: bool = False,
        max_jobs: Optional[int] = None,
        reuse_buffer: bool = True,
    ) -> int:
        """
        Iterate ratio jobs; compute each ratio series; call `process(job, series)`.

        `process` returns:
          - True  -> keep going
          - False -> stop early (useful for debugging / sampling)

        Returns number of processed jobs.
        """
        processed = 0
        buf = np.empty(self._X.shape[0], dtype=self._X.dtype) if reuse_buffer else None

        logger.info(
            "Scanning ratio universe: k_num=%d k_den=%d reuse_buffer=%s",
            k_num,
            k_den,
            reuse_buffer,
        )

        for job in self.iter_ratio_jobs(
            k_num=k_num,
            k_den=k_den,
            unordered_if_equal_k=unordered_if_equal_k,
            disallow_overlap=disallow_overlap,
            max_jobs=max_jobs,
        ):
            if buf is None:
                series = self.compute_ratio_series(job)
            else:
                self.compute_ratio_series_into(buf, job)
                series = buf

            processed += 1
            if not process(job, series):
                break

        logger.info("Completed scan: processed_jobs=%d", processed)
        return processed

    # ----------------------------
    # Optional: convenience to decode job -> symbols
    # ----------------------------
    def job_to_symbols(self, job: RatioJob) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        lib_num = self.get_basket_library(job.k_num)
        lib_den = lib_num if job.k_num == job.k_den else self.get_basket_library(job.k_den)

        num_idx = lib_num.baskets[job.num_id]
        den_idx = lib_den.baskets[job.den_id]

        num_syms = tuple(self.symbols[i] for i in num_idx)
        den_syms = tuple(self.symbols[i] for i in den_idx)
        return num_syms, den_syms


# -----------------------------------------------------------------------------
# Internal: fast overlap check for two sorted small integer arrays
# -----------------------------------------------------------------------------
def _has_overlap_sorted_ints(a: np.ndarray, b: np.ndarray) -> bool:
    """
    a and b are sorted 1D integer arrays (from combinations()).
    Two-pointer intersection in O(k).
    """
    i = 0
    j = 0
    na = a.size
    nb = b.size
    while i < na and j < nb:
        ai = int(a[i])
        bj = int(b[j])
        if ai == bj:
            return True
        if ai < bj:
            i += 1
        else:
            j += 1
    return False
