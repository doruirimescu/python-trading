"""Leakage harness: prefix invariance, future poison, engine-delay sanity.

A strategy is causal if its outputs at bar t depend only on bars <= t:
  * prefix invariance: outputs on data[:T] == the first T outputs on data[:T+k]
  * future poison: replacing every bar >= T by garbage leaves outputs < T unchanged
  * (event) trades fully closed before the cut are identical across prefix/poison runs
  * (event) the ORDER LOG (what on_bar decided at every bar <= T-1) is identical across prefix/poison runs. This is
    what catches a strategy that stashes the panel in prepare() and reads c[i+1] inside on_bar(): its features
    look causal, but the order it emits at the last bar before the cut differs once the future is poisoned.
  * cash and benchmark series are poisoned from the cut as well.
Cut points are sampled across the WHOLE dataset (each check runs on a bounded window ending shortly after the cut).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from ..config.schema import ExecCfg
from ..data.panel import Panel
from ..strategy.base import Strategy, features_to_arrays
from ..util.seeds import rng_for
from .event import run_event
from .vector import _signals, run_vector


@dataclass
class CausalityReport:
    strategy: str
    checks: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.checks)

    def add(self, name: str, ok: bool, detail: str = ""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d

    def summary(self) -> str:
        lines = [f"causality[{self.strategy}]: {'PASS' if self.ok else 'FAIL'}"]
        lines += [f"  {'ok  ' if c['ok'] else 'FAIL'} {c['name']}: {c['detail']}" for c in self.checks]
        return "\n".join(lines)


def poison_panel(panel: Panel, T: int, seed: int = 0) -> Panel:
    """Replace everything that is only known from bar position ``T`` on by extreme but structurally valid garbage:
    all bars at positions >= T, the cash series from the first session date after bar T-1's, and the benchmark
    series from the session date of bar T (a day's return is not known before that day ends)."""
    idx = panel.index
    if T >= len(idx):
        return panel
    cut_ts = idx[T]
    out = {}
    for s, b in panel.bars.items():
        b = b.copy()
        pos = int(b.index.searchsorted(cut_ts, side="left")) if len(b) else 0
        n = len(b) - pos
        if n > 0:
            rng = rng_for(seed, "poison", s)
            f = np.exp(rng.normal(0, 0.5, n))
            sl = slice(pos, None)
            for c in ("open", "close"):
                b.iloc[sl, b.columns.get_loc(c)] = b[c].to_numpy()[pos:] * f * rng.uniform(0.5, 2.0, n)
            op, cl = b["open"].to_numpy()[pos:], b["close"].to_numpy()[pos:]
            b.iloc[sl, b.columns.get_loc("high")] = np.maximum(op, cl) * (1 + rng.uniform(0, 1.0, n))
            b.iloc[sl, b.columns.get_loc("low")] = np.minimum(op, cl) * (1 - rng.uniform(0, 0.5, n))
            vf = rng.uniform(0.05, 20.0, n)
            for c in ("volume", "bid_vol", "ask_vol"):
                if c in b.columns:
                    b.iloc[sl, b.columns.get_loc(c)] = b[c].to_numpy()[pos:] * vf
        out[s] = b
    res = panel.with_bars(out)
    prim = panel.bars[panel.primary]
    prim_pos = int(prim.index.searchsorted(cut_ts, side="left"))
    if "session_date" in prim.columns and 0 < prim_pos < len(prim):
        d_prev = pd.Timestamp(prim["session_date"].iloc[prim_pos - 1])
        d_cut = pd.Timestamp(prim["session_date"].iloc[prim_pos])
        rng = rng_for(seed, "poison", "macro")
        if panel.benchmark is not None:
            bm = panel.benchmark.copy()
            m = np.asarray(bm.index >= d_cut) if isinstance(bm.index, pd.DatetimeIndex) else np.zeros(len(bm), bool)
            bm[m] = rng.normal(0.0, 0.05, int(m.sum()))
            res.benchmark = bm
        if panel.cash is not None:
            ca = panel.cash.copy()
            m = np.asarray(ca.index > d_prev) if isinstance(ca.index, pd.DatetimeIndex) else np.zeros(len(ca), bool)
            ca[m] = rng.uniform(-0.01, 0.01, int(m.sum())) + 0.005
            res.cash = ca
    return res


def _eq(a: np.ndarray, b: np.ndarray, tol: float = 1e-9) -> bool:
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        return False
    if a.dtype.kind in "fc" or b.dtype.kind in "fc":
        a, b = a.astype(float), b.astype(float)
        both_nan = np.isnan(a) & np.isnan(b)
        return bool(np.all(both_nan | (np.abs(a - b) <= tol * (1 + np.abs(a)))))
    return bool(np.all(a == b))


def _outputs(strategy: Strategy, panel: Panel) -> dict[str, np.ndarray]:
    if strategy.mode == "vector":
        return {"signals": _signals(panel, strategy)}
    return features_to_arrays(strategy.prepare(panel), panel[panel.primary].index)


def _closed_trades(res, before_ts) -> list[tuple]:
    t = res.trades
    if len(t) == 0:
        return []
    t = t[(t["exit_reason"] != "end_of_data") & (t["exit_ts"] < before_ts)]
    return [(r.entry_ts, r.side, round(float(r.qty), 8), round(float(r.entry_px), 8), r.exit_ts, round(float(r.exit_px), 8), r.exit_reason)
            for r in t.itertuples()]


def _window(panel: Panel, lo: int, hi: int) -> Panel:
    """Bars of the common index in positions [lo, hi) (by timestamp, so multi-symbol panels stay aligned)."""
    idx = panel.index
    t0, t1 = idx[lo], idx[hi - 1]
    return panel.with_bars({s: b[(b.index >= t0) & (b.index <= t1)] for s, b in panel.bars.items()})


def _session_start(panel: Panel, pos: int) -> int:
    """First bar position >= pos that opens a new session_date (so a window never starts mid-session)."""
    sd = panel.bars[panel.primary]["session_date"].to_numpy()
    n = len(sd)
    while 0 < pos < n and sd[pos] == sd[pos - 1]:
        pos += 1
    return min(pos, n)


def _orders_upto(log: list, last_bar: int) -> dict:
    return {j: o for j, o in log if j <= last_bar}


def check_causality(make_strategy: Callable[[], Strategy], panel: Panel, ex: ExecCfg, capital: float = 100_000.0, *,
                    cuts=(0.25, 0.55, 0.85), max_bars: int = 20_000, seed: int = 0,
                    extra_poison_cuts: int = 6) -> CausalityReport:
    """Run the leakage checks at several cut points spread over the whole dataset.

    Each cut T (a fraction of the full dataset) is tested on a window of at most ``max_bars`` bars that starts at a
    session boundary, ends k bars after the cut, and is run three ways: head(T), head(T+k) and head(T+k) with the
    future (>= T) poisoned. A one-bar peek only changes the decision at the very last bar before the cut, and it
    does so only when the poison happens to flip the strategy's trigger, so (event mode) the order log is also
    checked against ``extra_poison_cuts`` further poisoned runs with cuts a few bars earlier (T-9, T-18, ...).
    """
    n_full = len(panel.index)
    rep = CausalityReport(make_strategy().name)
    k = int(min(max(10, n_full // 10), max(10, max_bars // 5)))
    seen: set[int] = set()
    for frac in cuts:
        Tg = int(n_full * frac)                        # global cut position
        if Tg + k > n_full or Tg < 30:
            continue
        lo = _session_start(panel, max(0, Tg + k - max_bars))
        if lo >= Tg - 30 or Tg in seen:
            continue
        seen.add(Tg)
        base = _window(panel, lo, Tg + k)
        T = Tg - lo
        label = Tg
        a = make_strategy()
        b = make_strategy()
        pre = _outputs(a, base.head(T))
        ext = _outputs(b, base.head(T + k))
        poisoned_panel = poison_panel(base.head(T + k), T, seed)
        poisoned = _outputs(make_strategy(), poisoned_panel)
        bad_pre = [kname for kname in pre if kname in ext and not _eq(pre[kname], ext[kname][:T])]
        bad_poison = [kname for kname in pre if kname in poisoned and not _eq(pre[kname], poisoned[kname][:T])]
        rep.add(f"prefix_invariance@{label}", not bad_pre, f"features differing: {bad_pre}" if bad_pre else f"{len(pre)} outputs identical")
        rep.add(f"future_poison@{label}", not bad_poison, f"features differing: {bad_poison}" if bad_poison else f"{len(pre)} outputs identical")
        # trade-level / equity-level
        if a.mode == "vector":
            r1 = run_vector(base.head(T), make_strategy(), ex, capital)
            r2 = run_vector(base.head(T + k), make_strategy(), ex, capital)
            r3 = run_vector(poisoned_panel, make_strategy(), ex, capital)
            ok1 = _eq(r1.equity.to_numpy()[: T - 1], r2.equity.to_numpy()[: T - 1])
            ok2 = _eq(r1.equity.to_numpy()[: T - 1], r3.equity.to_numpy()[: T - 1])
            rep.add(f"equity_prefix@{label}", ok1 and ok2, "equity prefix identical" if ok1 and ok2 else "equity differs")
        else:
            l1, l2, l3 = [], [], []
            r1 = run_event(base.head(T), make_strategy(), ex, capital, order_log=l1)
            r2 = run_event(base.head(T + k), make_strategy(), ex, capital, order_log=l2)
            r3 = run_event(poisoned_panel, make_strategy(), ex, capital, order_log=l3)
            cut_ts = base[base.primary].index[T - 1]
            t1, t2, t3 = _closed_trades(r1, cut_ts), _closed_trades(r2, cut_ts), _closed_trades(r3, cut_ts)
            rep.add(f"trades_prefix@{label}", t1 == t2 and t1 == t3, f"{len(t1)} closed trades identical" if t1 == t2 == t3 else f"trades differ ({len(t1)}/{len(t2)}/{len(t3)})")
            # decisions: head(T) never decides at its last bar (T-1); the two longer runs do, with data <= T-1 only
            o1, o2, o3 = _orders_upto(l1, T - 2), _orders_upto(l2, T - 1), _orders_upto(l3, T - 1)
            ok_a = o1 == _orders_upto(l2, T - 2)
            ok_b = o2 == o3
            extra_bad = None
            for jx in range(1, extra_poison_cuts + 1):
                Tx = T - 9 * jx
                if Tx < 30:
                    break
                lx: list = []
                run_event(poison_panel(base.head(T + k), Tx, seed + jx), make_strategy(), ex, capital, order_log=lx)
                if _orders_upto(lx, Tx - 1) != _orders_upto(l2, Tx - 1):
                    extra_bad = Tx
                    ok_b = False
                    break
            first_bad = None
            if not (ok_a and ok_b):
                ref, other = (o1, _orders_upto(l2, T - 2)) if not ok_a else (o2, o3)
                bars_bad = sorted(j for j in set(ref) | set(other) if ref.get(j) != other.get(j))
                first_bad = bars_bad[0] if bars_bad else None
            rep.add(f"orders_prefix@{label}", ok_a and ok_b,
                    f"{len(o2)} decision bars identical (last checked bar {T - 1})" if ok_a and ok_b
                    else (f"orders differ at window bar {first_bad} (cut {T}): decision uses data after the cut" if extra_bad is None
                          else f"orders differ before window bar {extra_bad} when the future is poisoned from there: decision uses data after the cut"))
    if not rep.checks:
        rep.add("enough_data", False, f"need more bars (have {n_full})")
    return rep


class _Foresight(Strategy):
    """Oracle with PERFECT one-bar foresight (deliberately illegal): signal_t = sign(ret_{t+1})."""
    name = "_oracle_foresight"
    mode = "vector"

    def signals(self, data):
        c = data.field("close")
        return np.sign(c.shift(-1) / c - 1.0).fillna(0.0)


def _sharpe(r: pd.Series) -> float:
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(252)) if sd and sd > 0 else 0.0


def engine_delay_check(panel: Panel, capital: float = 100_000.0) -> dict:
    """Perfect-foresight-after-delay test of the ENGINE (independent of any strategy).

    An oracle that knows the next bar's return is run with same_close_unsafe (profits hugely: no delay)
    and with next_close (the signal's information is stale by the time it is filled: edge must vanish).

    The oracle flips its position almost every bar, so it is run at ZERO cost (the instrument's default commission
    would otherwise drag the delayed run to a large negative Sharpe that has nothing to do with look-ahead), and the
    "edge vanished" test is statistical: |Sharpe(next_close)| must be within 3 standard errors of zero
    (SE = sqrt(252 / n_days)) and below half of the unsafe Sharpe.
    """
    free = dict(commission_per_contract=0.0, commission_bps=0.0, slippage_ticks=0.0, slippage_bps=0.0,
                stop_extra_slippage_ticks=0.0)
    unsafe = run_vector(panel, _Foresight(), ExecCfg(fill="same_close_unsafe", allow_unsafe=True, **free), capital)
    safe = run_vector(panel, _Foresight(), ExecCfg(fill="next_close", **free), capital)
    nopen = run_vector(panel, _Foresight(), ExecCfg(fill="next_open", **free), capital)
    su, ss, so = _sharpe(unsafe.returns_daily), _sharpe(safe.returns_daily), _sharpe(nopen.returns_daily)
    nd = max(len(safe.returns_daily), 2)
    se = float(np.sqrt(252.0 / nd))
    return {"sharpe_unsafe": su, "sharpe_next_close": ss, "sharpe_next_open": so, "sharpe_se": se,
            "safe_final": float(safe.equity.iloc[-1]), "unsafe_final": float(unsafe.equity.iloc[-1]),
            "ok": bool(su > 5.0 and abs(ss) < max(3.0 * se, 1.5) and abs(ss) < 0.5 * su and so <= su * 1.1)}
