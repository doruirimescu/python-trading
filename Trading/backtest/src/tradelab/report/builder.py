"""``build_run_report``: the integration hook. Writes every run artifact and runs default analyses."""
from __future__ import annotations

import math
import traceback
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from tradelab.analytics import compute_metrics, daily_returns, periodic_tables
from tradelab.analytics.metrics import jsonable
from tradelab.robustness import (block_bootstrap, cost_sensitivity, count_trials, min_trl, pbo_cscv, psr, regime_breakdown,
                                 regime_summary, run_grid, sr_stats, trade_monte_carlo, verdict, walk_forward)
from tradelab.robustness.psr_dsr import dsr_from_stats

from . import run_dir as rd
from .summary_md import build_summary
from .tearsheet import ReportContext, render_tearsheet


def cfg_get(cfg: Any, path: str, default: Any = None) -> Any:
    """Dotted lookup through dicts / pydantic models / objects; default when missing."""
    cur = cfg
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return default if cur is None else cur


def _dump_cfg(cfg: Any) -> Any:
    if cfg is None:
        return None
    if hasattr(cfg, "model_dump"):
        return cfg.model_dump(mode="json")
    return cfg


def _safe(errors: dict, name: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as e:
        errors[name] = f"{type(e).__name__}: {e}"
        errors[f"{name}__trace"] = traceback.format_exc()[-600:]
        return None


def run_default_analyses(result: Any, metrics: dict, run_fn: Callable | None, cfg: Any, extras: dict, rd_dir: Path | None = None,
                         ppy: int = 252) -> tuple[dict, dict]:
    """Returns (robustness_json, objs). ``objs`` holds non-JSON objects (grid, samples, tables) for the tearsheet."""
    extras = extras or {}
    errors: dict[str, str] = {}
    rob: dict[str, Any] = {}
    objs: dict[str, Any] = {}
    seed = int(cfg_get(cfg, "robustness.seed", (result.meta or {}).get("seed", 42)) or 42)
    r = daily_returns(result)

    # PSR / MinTRL
    s = sr_stats(r)
    rob["psr"] = {"psr0": psr(r, 0.0), "min_trl_days": min_trl(r, 0.0), "T": s["T"], "sr_per_period": s["sr"], "skew": s["skew"], "kurt": s["kurt"]}
    # bootstrap + monte carlo
    bs = _safe(errors, "bootstrap", lambda: block_bootstrap(r, n=int(cfg_get(cfg, "robustness.bootstrap_n", 2000)), seed=seed, periods_per_year=ppy))
    if bs is not None:
        rob["bootstrap"], objs["bootstrap"] = bs.summary, bs
    tr = getattr(result, "trades", None)
    if tr is not None and len(tr) >= 5 and (result.meta or {}).get("mode") != "vector":   # vector trades are approximate/compounded
        mc = _safe(errors, "monte_carlo", lambda: trade_monte_carlo(tr, n=int(cfg_get(cfg, "robustness.mc_n", 2000)), seed=seed,
                                                                    initial_capital=float(result.initial_capital)))
        if mc is not None and mc.summary.get("n"):
            rob["monte_carlo"], objs["monte_carlo"] = mc.summary, mc
    # regimes
    rg = _safe(errors, "regimes", lambda: regime_breakdown(result, periods_per_year=ppy))
    if rg:
        objs["regimes"] = rg
        rob["regimes"] = regime_summary(rg)
    # cost sensitivity
    cost_variants = cfg_get(cfg, "robustness.cost_variants", None) or extras.get("cost_variants")
    if run_fn is not None:
        cs = _safe(errors, "cost_sensitivity", lambda: cost_sensitivity(
            run_fn, dict((result.meta or {}).get("params", {}) or {}), tuple(cfg_get(cfg, "robustness.cost_mults", (0, 1, 2, 3))),
            variants=cost_variants, periods_per_year=ppy))
        if cs is not None:
            objs["cost_table"] = cs["table"]
            rob["cost_sensitivity"] = {"table": cs["table"].to_dict(orient="records"), "breakeven_cost_mult": cs["breakeven_cost_mult"],
                                       "positive_at_2x": cs["positive_at_2x"]}
    # grid (provided or requested by cfg)
    grid = extras.get("grid")
    grid_spec = cfg_get(cfg, "robustness.grid", None)
    if grid is None and grid_spec and run_fn is not None:
        grid = _safe(errors, "grid", lambda: run_grid(run_fn, dict(grid_spec), cfg_get(cfg, "robustness.objective", "sharpe"),
                                                      int(cfg_get(cfg, "robustness.n_jobs", 1)), seed, periods_per_year=ppy))
    n_trials = extras.get("n_trials")
    ledger = extras.get("trial_ledger")
    if grid is not None:
        objs["grid"] = grid
        rob["grid"] = grid.to_dict()
        n_trials = max(int(n_trials or 0), grid.n_trials)
        if grid.returns_matrix.shape[1] >= 2:
            pb = _safe(errors, "pbo", lambda: pbo_cscv(grid.returns_matrix, n_slices=int(cfg_get(cfg, "robustness.pbo_slices", 16)), seed=seed))
            if pb is not None:
                objs["pbo_logits"] = pb.get("logits")
                rob["pbo"] = {k: v for k, v in pb.items() if k != "logits"}
    if ledger is not None:
        n_trials = max(int(n_trials or 0), count_trials(ledger))
    sr_var = extras.get("sr_variance") or (grid.sr_variance if grid is not None else None)
    if n_trials and n_trials > 1 and sr_var is not None and math.isfinite(sr_var):
        d = dsr_from_stats(s["sr"], s["T"], s["skew"], s["kurt"], int(n_trials), float(sr_var))
        rob["psr"].update(dsr=d, n_trials=int(n_trials), sr_variance=float(sr_var))
    # walk-forward (provided or requested)
    wf = extras.get("walkforward")
    wf_spec = cfg_get(cfg, "robustness.walkforward", None)
    if wf is None and wf_spec and run_fn is not None and grid_spec:
        spec = dict(wf_spec)
        wf = _safe(errors, "walkforward", lambda: walk_forward(run_fn, dict(grid_spec), pd.DatetimeIndex(r.index), spec["is_len"], spec["oos_len"],
                                                                spec.get("step"), spec.get("scheme", "rolling"), spec.get("purge", 0),
                                                                cfg_get(cfg, "robustness.objective", "sharpe"), periods_per_year=ppy,
                                                                initial_capital=float(result.initial_capital)))
    if wf is not None:
        objs["walkforward"] = wf
        rob["walkforward"] = {k: v for k, v in wf.to_dict().items() if k != "folds"}
    # integrity (supplied by the CLI): causality check + data quality
    caus = extras.get("causality")
    if caus is not None:
        rob["causality"] = {"ok": bool(caus.get("ok")), "checks": [{"name": c["name"], "ok": c["ok"]} for c in caus.get("checks", [])]}
    dq = extras.get("data_quality")
    if dq:
        rob["data_quality"] = {s_: {"ok": q.get("ok", not q.get("n_errors", 0)), "n_bars": q.get("n_bars"),
                                    "issues": [f"{i.get('severity')}:{i.get('code')}x{i.get('count')}" for i in q.get("issues", [])]}
                               for s_, q in dq.items() if isinstance(q, dict)}
    # verdict
    rob["verdict"] = verdict(
        dsr=rob["psr"].get("dsr"), pbo=rob.get("pbo", {}).get("pbo"), wf_efficiency=rob.get("walkforward", {}).get("efficiency"),
        positive_at_2x=rob.get("cost_sensitivity", {}).get("positive_at_2x"), n_trades=metrics.get("trades", {}).get("n_trades"),
        plateau=rob.get("grid", {}).get("plateau_score"), psr0=rob["psr"].get("psr0"))
    if errors:
        rob["errors"] = {k: v for k, v in errors.items() if not k.endswith("__trace")}
        rob["error_traces"] = {k: v for k, v in errors.items() if k.endswith("__trace")}
    return jsonable(rob), objs


def build_run_report(run_dir: str | Path, result: Any, panel: Any = None, cfg: Any = None, run_fn: Callable | None = None,
                     extras: dict | None = None) -> Path:
    """Write the full artifact set into ``run_dir`` and return it.

    Files: metrics.json, summary.md, tearsheet.html, robustness.json, equity.parquet, returns_daily.csv, trades.csv, costs_daily.csv,
    tables/*.csv, config.resolved.yaml (if cfg), env.json, grid_results.parquet + walkforward.json (if provided/requested).
    ``extras`` keys: grid (GridResult), walkforward (WalkForwardResult), n_trials, sr_variance, trial_ledger (path),
    data_quality (dict), cost_variants (dict), ``periods_per_year``. Never raises on a failing analysis: errors are recorded in robustness.json.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    extras = dict(extras or {})
    ppy = int(extras.get("periods_per_year") or cfg_get(cfg, "analytics.periods_per_year", 252) or 252)
    files = rd.write_core_artifacts(run_dir, result)
    metrics = compute_metrics(result, periods_per_year=ppy)
    rd.write_json(run_dir / "metrics.json", metrics)
    files.append("metrics.json")
    tables = periodic_tables(result)
    for name, t in tables.items():
        rd.write_csv(run_dir / "tables" / f"{name}.csv", t)
    if tables:
        files.append("tables/*.csv")
    rob, objs = run_default_analyses(result, metrics, run_fn, cfg, extras, run_dir, ppy)
    rd.write_json(run_dir / "robustness.json", rob)
    files.append("robustness.json")
    g = objs.get("grid")
    if g is not None:
        try:
            g.table.to_parquet(run_dir / "grid_results.parquet")
            files.append("grid_results.parquet")
        except Exception:
            rd.write_csv(run_dir / "grid_results.csv", g.table, index=False)
            files.append("grid_results.csv")
    wf = objs.get("walkforward")
    if wf is not None:
        rd.write_json(run_dir / "walkforward.json", wf.to_dict())
        files.append("walkforward.json")
    if objs.get("regimes"):
        for name, t in objs["regimes"].items():
            rd.write_csv(run_dir / "tables" / f"regime_{name}.csv", t)
    if extras.get("data_quality") is not None and not (run_dir / "data_quality.json").exists():
        rd.write_json(run_dir / "data_quality.json", extras["data_quality"])
        files.append("data_quality.json")
    if cfg is not None and not (run_dir / "config.resolved.yaml").exists():
        try:
            import yaml
            (run_dir / "config.resolved.yaml").write_text(yaml.safe_dump(jsonable(_dump_cfg(cfg)), sort_keys=False), encoding="utf-8")
            files.append("config.resolved.yaml")
        except Exception:
            pass
    if not (run_dir / "env.json").exists():
        rd.write_json(run_dir / "env.json", rd.env_info((result.meta or {}).get("seed")))
        files.append("env.json")
    ctx = ReportContext(result=result, metrics=metrics, tables=tables, robustness=rob, objs=objs, panel=panel, cfg=cfg, extras=extras)
    (run_dir / "tearsheet.html").write_text(render_tearsheet(ctx), encoding="utf-8")
    files.append("tearsheet.html")
    files.append("summary.md")
    (run_dir / "summary.md").write_text(build_summary(metrics, rob, sorted(set(files))), encoding="utf-8")
    return run_dir
