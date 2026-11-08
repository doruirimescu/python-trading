"""Agent-parseable summary.md: fixed headings, ``- key: value`` lines, < ~100 lines."""
from __future__ import annotations

from typing import Any

HEADINGS = ["# Run summary", "## Meta", "## Headline metrics", "## Trades", "## R-multiples", "## Benchmark",
            "## Integrity", "## Robustness", "## Cost sensitivity", "## Warnings", "## Files"]


def _f(v: Any, nd: int = 4) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, float):
        return f"{v:.{max(nd, 7) if abs(v) >= 1e4 else nd}g}"
    return str(v)


def _kv(d: dict, keys: list[str]) -> list[str]:
    return [f"- {k}: {_f(d.get(k))}" for k in keys if k in d]


def warnings_for(metrics: dict, robustness: dict) -> list[str]:
    w = []
    n = metrics.get("trades", {}).get("n_trades", 0)
    if n < 30:
        w.append(f"very few trades ({n}); statistics are unreliable")
    elif n < 100:
        w.append(f"fewer than 100 trades ({n})")
    if robustness.get("causality") and not robustness["causality"]["ok"]:
        w.append("CAUSALITY CHECK FAILED: the strategy uses future information; do not trust any number above")
    p = robustness.get("psr", {})
    if p.get("psr0") is not None and p["psr0"] < 0.95:
        w.append(f"PSR(0)={p['psr0']:.2f} < 0.95: Sharpe not statistically distinguishable from 0")
    if p.get("min_trl_days") is not None and p.get("T") and p["min_trl_days"] > p["T"]:
        w.append(f"track record shorter than MinTRL ({p['T']} < {p['min_trl_days']:.0f} days)")
    cs = robustness.get("cost_sensitivity", {})
    if cs.get("positive_at_2x") is False:
        w.append("not profitable at 2x costs")
    if robustness.get("pbo", {}).get("pbo") not in (None,) and robustness["pbo"]["pbo"] >= 0.5:
        w.append(f"PBO={robustness['pbo']['pbo']:.2f} >= 0.5: likely overfit selection")
    for k, e in (robustness.get("errors") or {}).items():
        w.append(f"{k} failed: {e}")
    return w


def build_summary(metrics: dict, robustness: dict, files: list[str]) -> str:
    L: list[str] = ["# Run summary", "", "## Meta"]
    meta = metrics.get("meta", {})
    for k in ("strategy", "freq", "mode", "seed", "config_hash", "data_fingerprint"):
        if k in meta:
            L.append(f"- {k}: {_f(meta[k])}")
    if "params" in meta:
        L.append(f"- params: {meta['params']}")
    L += _kv(metrics, ["start", "end", "n_days", "initial_capital", "final_equity"])
    L += ["", "## Headline metrics"]
    L += _kv(metrics, ["total_return", "cagr", "annual_vol", "sharpe", "sortino", "calmar", "max_drawdown", "max_dd_duration_days",
                       "time_to_recovery_days", "ulcer_index", "skew", "kurtosis_excess", "cvar_95_hist",
                       "worst_day", "exposure", "total_costs"])
    L += ["", "## Trades"]
    L += _kv(metrics.get("trades", {}), ["n_trades", "hit_rate", "profit_factor", "payoff_ratio", "expectancy",
                                         "avg_bars_held", "trades_per_day", "max_consecutive_losses", "total_net_pnl"])
    L += ["", "## R-multiples"]
    L += _kv(metrics.get("rmultiple", {}), ["expectancy_r", "sqn", "best_r", "worst_r", "avg_mae_r", "avg_mfe_r"])
    bm = metrics.get("benchmark", {})
    L += ["", "## Benchmark"]
    L += _kv(bm, ["alpha_annual", "beta", "correlation", "information_ratio", "bh_cagr", "excess_cagr"]) or ["- none: no benchmark supplied"]
    L += ["", "## Integrity"]
    c = robustness.get("causality")
    L.append(f"- causality: {'PASS' if c['ok'] else 'FAIL (LEAK - results invalid)'}" if c else "- causality: not run")
    for sym, q in (robustness.get("data_quality") or {}).items():
        L.append(f"- data_quality[{sym}]: {'ok' if q.get('ok') else 'ERRORS'}, bars={q.get('n_bars')}, issues={', '.join(q.get('issues') or []) or 'none'}")
    L += ["", "## Robustness"]
    v = robustness.get("verdict", {})
    L.append(f"- verdict: {v.get('overall', 'n/a')} (advisory)")
    if v.get("checks"):
        L.append("- checks: " + ", ".join(f"{c['check']}={c['status']}({_f(c['value'], 3)})" for c in v["checks"]))
    p = robustness.get("psr", {})
    L += _kv(p, ["psr0", "min_trl_days", "dsr", "n_trials", "sr_per_period"])
    b = robustness.get("bootstrap", {})
    L += [f"- bootstrap.{k}: {_f(b[k])}" for k in ("prob_sharpe_gt_0", "sharpe_p05", "sharpe_p95", "max_drawdown_p05") if k in b]
    mc = robustness.get("monte_carlo", {})
    L += [f"- monte_carlo.{k}: {_f(mc[k])}" for k in ("risk_of_ruin", "max_drawdown_p05") if k in mc]
    if "pbo" in robustness:
        L += [f"- pbo: {_f(robustness['pbo'].get('pbo'))}"]
    if "grid" in robustness:
        g = robustness["grid"]
        L += [f"- grid.best_params: {g.get('best_params')}", f"- grid.plateau_score: {_f(g.get('plateau_score'))}", f"- grid.n_trials: {_f(g.get('n_trials'))}"]
    if "walkforward" in robustness:
        w = robustness["walkforward"]
        L += [f"- walkforward.efficiency: {_f(w.get('efficiency'))}", f"- walkforward.oos_sharpe: {_f(w.get('oos_sharpe'))}", f"- walkforward.n_folds: {_f(w.get('n_folds'))}"]
    rs = robustness.get("regimes", {})
    if rs:
        L.append(f"- regimes.negative: {rs.get('n_negative')}/{rs.get('n_regimes')} (worst: {rs.get('worst', {}).get('table')}={rs.get('worst', {}).get('label')})")
    L += ["", "## Cost sensitivity"]
    cs = robustness.get("cost_sensitivity", {})
    if cs.get("table"):
        L += ["| label | cost_mult | total_return | sharpe | n_trades |", "|---|---|---|---|---|"]
        L += [f"| {r['label']} | {_f(r.get('cost_mult'))} | {_f(r.get('total_return'))} | {_f(r.get('sharpe'))} | {r.get('n_trades')} |" for r in cs["table"]]
        L += [f"- breakeven_cost_mult: {_f(cs.get('breakeven_cost_mult'))}", f"- positive_at_2x: {_f(cs.get('positive_at_2x'))}"]
    else:
        L.append("- none: no run_fn supplied")
    L += ["", "## Warnings"]
    L += [f"- {w}" for w in warnings_for(metrics, robustness)] or ["- none"]
    L += ["", "## Files", "- " + ", ".join(files)]
    return "\n".join(L) + "\n"
