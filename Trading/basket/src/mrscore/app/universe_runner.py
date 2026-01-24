from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence

import numpy as np

from mrscore.config.loader import load_config
from mrscore.io.history import History, OHLC
from mrscore.io.adapters import build_price_panel, compute_returns_from_prices
from mrscore.core.ratio_universe import RatioUniverse, RatioJob

# Replace with your actual engine/scorer import once implemented
# from mrscore.core.engine import MeanReversionEngine


@dataclass(frozen=True)
class UniverseRunResult:
    processed_jobs: int
    stopped_early: bool


def run_ratio_universe(
    *,
    config_path: str,
    histories: Dict[str, History],
    symbols: Sequence[str],
    field: OHLC = OHLC.CLOSE,
    k_num: int = 3,
    k_den: int = 3,
    disallow_overlap: bool = True,
    unordered_if_equal_k: bool = True,
    max_jobs: Optional[int] = None,
    on_result: Optional[Callable[[RatioJob, dict], None]] = None,
) -> UniverseRunResult:
    """
    Skeleton runner:
      - loads config (Pydantic validated)
      - builds aligned panel from histories (adapter)
      - streams ratios (RatioUniverse)
      - computes per-ratio returns if configured
      - calls into your engine/scorer (placeholder)
    """
    runtime = load_config(config_path).raw

    # 1) Adapter: build a dense aligned panel (intersection alignment + per-symbol normalization)
    panel = build_price_panel(
        histories=histories,
        symbols=symbols,
        field=field,
        align="intersection",          # strict intersection recommended for statistical comparability
        normalize_by_first=True,       # per-symbol normalization (vectorized)
    )

    # 2) Universe: do NOT normalize again inside RatioUniverse
    ru = RatioUniverse(
        panel=panel,
        normalize_by_first=False,      # already normalized by adapter
        eps=1e-12,
    )

    # 3) Preallocate buffers to minimize allocations during scanning
    T = panel.values.shape[0]
    ratio_buf = np.empty(T, dtype=np.float64)        # ratio price series
    ret_buf = np.empty(T - 1, dtype=np.float64)      # returns series (if needed)

    returns_mode = runtime.data.returns_mode  # "log" | "simple" | "none"

    stopped_early = False

    def process(job: RatioJob, series_view: np.ndarray) -> bool:
        """
        Called by RatioUniverse for each ratio series.
        We deliberately reuse buffers. `series_view` may be the reusable buffer from RatioUniverse.
        """
        nonlocal stopped_early

        # If RatioUniverse gave us a view into its own buffer, copy into our stable buffer
        # (optional; if you can guarantee the engine consumes immediately, you can avoid this copy)
        ratio_buf[:] = series_view

        # Returns if needed (volatility estimators typically want returns)
        if returns_mode == "none":
            returns = None
        else:
            # Fast, vectorized returns into ret_buf
            if returns_mode == "simple":
                # ret = p1/p0 - 1
                np.divide(ratio_buf[1:], ratio_buf[:-1], out=ret_buf)
                ret_buf -= 1.0
            elif returns_mode == "log":
                # ret = log(p1) - log(p0)
                # Note: np.log allocates unless you provide an out buffer.
                # We'll reuse temp buffers by doing log in-place into two slices via a small temp.
                # For simplicity here, we accept two logs; optimize later if needed.
                np.log(ratio_buf[1:], out=ret_buf)              # ret_buf = log(p1)
                tmp = np.log(ratio_buf[:-1])                    # allocates; optimize later if this becomes hot
                ret_buf -= tmp
            else:
                raise ValueError(f"Invalid returns_mode: {returns_mode}")
            returns = ret_buf

        # 4) Engine/scorer call (placeholder)
        # score = engine.run(prices=ratio_buf, returns=returns, dates=ru.dates)
        score = {
            "job": job,
            "example_metric": float(np.nanmean(ratio_buf)),  # placeholder
        }

        if on_result is not None:
            on_result(job, score)

        return True  # return False to stop early

    # 5) Scan universe (stream jobs, reuse RatioUniverse buffer)
    processed = ru.scan(
        k_num=k_num,
        k_den=k_den,
        process=process,
        unordered_if_equal_k=unordered_if_equal_k,
        disallow_overlap=disallow_overlap,
        max_jobs=max_jobs,
        reuse_buffer=True,
    )

    return UniverseRunResult(processed_jobs=processed, stopped_early=stopped_early)
