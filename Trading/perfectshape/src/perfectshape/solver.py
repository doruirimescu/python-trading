"""Basket weight solvers.

Prices in a window are normalised to 1.0 at the window start (``X``, shape (T, n)), so a basket with capital
weights ``w`` (sum 1, held as fixed shares) has value ``V = X @ w``, starting at 1.0.

* ``trend_tstat`` - maximise the t-stat of the basket's linear slope: |slope| / residual-std around the
  fitted line. With R = cov of each asset's residual around its own line and c = asset slopes, the optimum
  is ``w ~ R^-1 c * direction`` (a tangency portfolio of "trend" vs "noise"), then scaled to sum 1.
* ``range_ratio`` - minimise drift relative to oscillation: w'Aw / w'Bw, where A is the covariance of each
  asset's quadratic trend component and B the covariance of what remains (the swings). Smallest
  generalised eigenvector.

Both are scale invariant, so normalising to sum(w) = 1 is free as long as sum(u) has the right sign.
Bounds (long-only, max weight) are enforced by clip-and-renormalise, which is exact when no bound binds
and a good feasible approximation otherwise; the scorer judges the result either way.

:class:`Solver` precomputes the n x n matrices once per window and then solves "basket S + candidate j"
for every candidate j in one batched numpy call.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from perfectshape.shapes import poly_fit


@dataclass
class Bounds:
    long_only: bool = True
    max_weight: float = 0.7


def project_weights(W: np.ndarray, bounds: Bounds) -> np.ndarray:
    """Make rows of W feasible: sum 1, each weight in [lo, cap] (lo = 0 long-only, else -cap).

    Rows already feasible are untouched. Others: clip below, renormalise, then cap-and-redistribute the
    excess proportionally over the uncapped members. Rows that cannot be made feasible become NaN.
    """
    W = np.array(W, dtype=np.float64, copy=True)
    k = W.shape[1]
    cap = bounds.max_weight if k * bounds.max_weight >= 1.0 else 1.0
    lo = 0.0 if bounds.long_only else -cap
    bad = ~np.all((W >= lo - 1e-9) & (W <= cap + 1e-9), axis=1) & ~np.isnan(W).any(axis=1)
    if bad.any():
        W[bad] = _project_rows(W[bad], lo, cap)
    return W


def _row_sums(w: np.ndarray) -> np.ndarray:
    """Row sums added in the order numpy sums one short row (left to right below 8, pairwise from 8), so the
    batched projection matches projecting row by row to the last bit."""
    k = w.shape[1]
    if k < 8:
        out = np.zeros(len(w))
        for j in range(k):
            out = out + w[:, j]
        return out
    if k == 8:
        return ((w[:, 0] + w[:, 1]) + (w[:, 2] + w[:, 3])) + ((w[:, 4] + w[:, 5]) + (w[:, 6] + w[:, 7]))
    return np.array([r.sum() for r in w])


def _project_rows(W: np.ndarray, lo: float, cap: float) -> np.ndarray:
    """Clip, renormalise, cap-and-redistribute every row of W at once (a row stops when nothing is over)."""
    w = np.clip(W, lo, None)
    s = _row_sums(w)
    dead = s <= 1e-12
    with np.errstate(divide="ignore", invalid="ignore"):
        w = w / s[:, None]
        fixed = np.zeros(w.shape, dtype=bool)
        for _ in range(w.shape[1]):
            over = (w > cap + 1e-12) & ~fixed
            act = over.any(axis=1) & ~dead
            if not act.any():
                break
            fixed |= over & act[:, None]
            free = ~fixed
            rem = 1.0 - cap * fixed.sum(axis=1)
            # the free members only, left to right (at least one member is fixed, so fewer than 8 of them)
            fs = np.zeros(len(w))
            for j in range(w.shape[1]):
                fs = fs + np.where(free[:, j], w[:, j], 0.0)
            spread = np.where((fs > 1e-12)[:, None], w * rem[:, None] / fs[:, None],
                              (rem / np.maximum(free.sum(axis=1), 1))[:, None])
            w = np.where(act[:, None], np.where(fixed, cap, spread), w)
    ok = ~dead & ~np.any(w < lo - 1e-9, axis=1) & ~np.any(w > cap + 1e-9, axis=1)
    w[~ok] = np.nan
    return w


class Solver:
    def __init__(self, X: np.ndarray, objective: str, direction: int = 0, ridge: float = 1e-4):
        self.X = X
        self.objective = objective
        self.direction = direction
        self.ridge = ridge
        T = X.shape[0]
        if objective == "trend_tstat":
            tau = np.linspace(0.0, 1.0, T)
            tc = tau - tau.mean()
            xm = X.mean(axis=0)
            self.c = (tc @ (X - xm)) / (tc @ tc)
            Z = X - xm - np.outer(tc, self.c)
            self.R = Z.T @ Z / T
        elif objective == "range_ratio":
            F = poly_fit(X, 2)
            D = F - F.mean(axis=0)
            E = X - F
            self.A = D.T @ D / T
            self.B = E.T @ E / T
        else:
            raise ValueError(f"unknown objective {objective!r}")

    def solve(self, basket: list[int], candidates: np.ndarray, bounds: Bounds) -> np.ndarray:
        """Weights for every basket ``basket + [j]``, j in candidates. Returns (J, len(basket)+1), NaN rows = infeasible."""
        cand = np.asarray(candidates, dtype=np.int64)
        J = len(cand)
        idx = np.empty((J, len(basket) + 1), dtype=np.int64)
        idx[:, :-1] = np.asarray(basket, dtype=np.int64)
        idx[:, -1] = cand
        return self.solve_sets(idx, bounds)

    def solve_sets(self, idx: np.ndarray, bounds: Bounds) -> np.ndarray:
        J, k = idx.shape
        if k == 1:
            return np.ones((J, 1))
        eye = np.eye(k)[None]
        if self.objective == "trend_tstat":
            Rb = self.R[idx[:, :, None], idx[:, None, :]]
            Rb = Rb + self.ridge * _mean_diag(Rb)[:, None, None] * eye
            u = np.linalg.solve(Rb, (self.c[idx] * self.direction)[..., None])[..., 0]
            ok = u.sum(axis=1) > 1e-12 * np.abs(u).sum(axis=1)
        else:
            Ab = self.A[idx[:, :, None], idx[:, None, :]]
            Bb = self.B[idx[:, :, None], idx[:, None, :]]
            Bb = Bb + self.ridge * _mean_diag(Bb)[:, None, None] * eye + 1e-18 * eye
            L = np.linalg.cholesky(Bb)
            Linv = np.linalg.inv(L)
            C = Linv @ Ab @ np.swapaxes(Linv, 1, 2)
            _, vecs = np.linalg.eigh((C + np.swapaxes(C, 1, 2)) / 2)
            y = vecs[:, :, 0]
            u = (np.swapaxes(Linv, 1, 2) @ y[..., None])[..., 0]
            ok = np.abs(u.sum(axis=1)) > 1e-6 * np.abs(u).sum(axis=1)
        s = np.where(ok, u.sum(axis=1), 1.0)
        W = u / s[:, None]
        W[~ok] = np.nan
        return project_weights(W, bounds)

    def curves(self, idx: np.ndarray, W: np.ndarray) -> np.ndarray:
        """Basket value curves (T, J) for index sets (J, k) and weights (J, k)."""
        return np.einsum("tjk,jk->tj", self.X[:, idx], np.nan_to_num(W))


def _mean_diag(M: np.ndarray) -> np.ndarray:
    return np.maximum(np.einsum("jii->j", M) / M.shape[1], 1e-18)
