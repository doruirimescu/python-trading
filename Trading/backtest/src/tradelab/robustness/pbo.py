"""Probability of Backtest Overfitting via CSCV (Bailey, Borwein, Lopez de Prado, Zhu 2015)."""
from __future__ import annotations

from itertools import combinations
from math import comb

import numpy as np
import pandas as pd


def pbo_cscv(returns_matrix: pd.DataFrame, n_slices: int = 16, max_combos: int = 2000, seed: int = 42) -> dict:
    """returns_matrix: rows = time (daily), columns = strategy configurations (trials).

    Splits rows into ``n_slices`` contiguous blocks; for every (sampled) choice of S/2 blocks as IS
    (rest OOS) picks the IS-best config by Sharpe (mean/std), ranks it OOS, logit lambda = ln(w/(1-w)),
    w = rank/(N+1). PBO = share of combos with lambda <= 0 (IS winner at/below OOS median).
    """
    if n_slices % 2:
        raise ValueError("n_slices must be even")
    m = returns_matrix.dropna(how="all").fillna(0.0)
    T, N = m.shape
    if N < 2:
        return {"pbo": float("nan"), "n_configs": N, "n_combos": 0, "logits": [], "note": "need >=2 configs"}
    L = T // n_slices
    if L < 2:
        raise ValueError("not enough rows for n_slices")
    x = m.to_numpy(float)[T - L * n_slices:]
    blocks = x.reshape(n_slices, L, N)
    s1 = blocks.sum(axis=1)               # (S, N)
    s2 = (blocks**2).sum(axis=1)
    half = n_slices // 2
    total = comb(n_slices, half)
    if total <= max_combos:
        combos = np.array(list(combinations(range(n_slices), half)))
    else:
        rng = np.random.default_rng(seed)
        seen: set[tuple[int, ...]] = set()
        while len(seen) < max_combos:
            seen.add(tuple(sorted(rng.choice(n_slices, half, replace=False).tolist())))
        combos = np.array(sorted(seen))
    mask = np.zeros((len(combos), n_slices), bool)
    np.put_along_axis(mask, combos, True, axis=1)

    def sharpe(sel: np.ndarray) -> np.ndarray:
        n = sel.sum(axis=1, keepdims=True) * L
        a = sel.astype(float) @ s1
        b = sel.astype(float) @ s2
        mean = a / n
        var = (b - n * mean**2) / (n - 1)
        sd = np.sqrt(np.maximum(var, 1e-18))
        return mean / sd

    is_sr, oos_sr = sharpe(mask), sharpe(~mask)
    best = is_sr.argmax(axis=1)
    rows = np.arange(len(combos))
    oos_best = oos_sr[rows, best]
    rank = (oos_sr < oos_best[:, None]).sum(axis=1) + 1 + 0.5 * ((oos_sr == oos_best[:, None]).sum(axis=1) - 1)
    w = rank / (N + 1.0)
    logit = np.log(w / (1 - w))
    pbo = float((logit <= 0).mean())
    is_best = is_sr[rows, best]
    slope = float(np.polyfit(is_best, oos_best, 1)[0]) if np.std(is_best) > 0 else float("nan")
    return {
        "pbo": pbo, "n_configs": int(N), "n_combos": int(len(combos)), "n_slices": n_slices,
        "prob_oos_loss": float((oos_best < 0).mean()),
        "oos_perf_degradation_slope": slope,
        "mean_is_best_sr": float(is_best.mean()), "mean_oos_of_is_best_sr": float(oos_best.mean()),
        "logits": logit.tolist(),
    }
