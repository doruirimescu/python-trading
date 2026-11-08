"""tradelab command line: python -m tradelab <command> ..."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

from . import __version__
from .config.loader import load_config, resolved_dict
from .data.cache import project_root
from .data.panel import load_panel
from .data.sources import list_sources
from .engine.causality import check_causality, engine_delay_check
from .engine.runner import build_strategy, config_hash, make_run_fn, run_strategy
from .strategy.registry import get_strategy, list_strategies
from .util.clock import run_stamp


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=project_root(), capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None


def _env() -> dict:
    import numpy
    import pandas
    import scipy

    return {"python": sys.version.split()[0], "platform": platform.platform(), "tradelab": __version__,
            "numpy": numpy.__version__, "pandas": pandas.__version__, "scipy": scipy.__version__, "git_sha": _git_sha()}


def _extra_dirs(cfg):
    return [cfg.strategy.path] if cfg.strategy.path else None


EXIT_OK, EXIT_CONFIG, EXIT_DATA, EXIT_LEAK = 0, 2, 3, 4


class CliError(Exception):
    def __init__(self, msg: str, code: int):
        super().__init__(msg)
        self.code = code


def _ppy(cfg) -> int:
    return int(cfg.analytics.periods_per_year or cfg.periods_per_year)


def _resolve_grid(cfg) -> dict | None:
    g = cfg.strategy.grid
    if g is None:
        return None
    if g == "auto":
        from .strategy.params import grid_axes

        extra = [cfg.strategy.path] if cfg.strategy.path else None
        g = grid_axes(get_strategy(cfg.strategy.name, extra).Params)
        if not g:
            raise CliError("strategy.grid: auto but the strategy Params declare no grid(...) hints", EXIT_CONFIG)
    return {k: list(v) for k, v in g.items()}


def _load(a):
    from pydantic import ValidationError

    try:
        cfg = load_config(a.config)
    except (ValidationError, yaml.YAMLError, FileNotFoundError) as e:
        raise CliError(f"config error: {e}", EXIT_CONFIG)
    if getattr(a, "refresh", False):
        cfg.data.refresh = True
    return cfg


def _load_panel(cfg):
    from .data.quality import DataQualityError

    try:
        return load_panel(cfg.data)
    except (DataQualityError, ConnectionError, OSError, RuntimeError) as e:
        raise CliError(f"data error: {type(e).__name__}: {e}", EXIT_DATA)
    except KeyError as e:
        raise CliError(f"data error: unknown source or symbol {e}", EXIT_DATA)


def _build(cfg):
    try:
        return build_strategy(cfg)
    except Exception as e:  # unknown strategy / bad params
        raise CliError(f"config error: {type(e).__name__}: {e}", EXIT_CONFIG)


def _git(cmd_args) -> str | None:
    try:
        return subprocess.run(["git", *cmd_args], cwd=project_root(), capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None


def _execute(cfg, out: Path, *, want_grid: bool, want_wf: bool, no_causality: bool = False, use_best: bool = False,
             run_dir: Path | None = None, command: str = "run") -> tuple[Path, int]:
    """Shared pipeline of run / optimize / walkforward / report. Returns (run_dir, exit_code)."""
    from .report import build_run_report, make_run_dir, update_latest
    from .robustness import count_trials, run_grid, trial_ledger_append, walk_forward

    panel = _load_panel(cfg)
    strat = _build(cfg)
    h = config_hash(cfg)
    ppy = _ppy(cfg)
    rb = cfg.robustness
    seed = rb.seed if rb.seed is not None else cfg.seed
    run_fn = make_run_fn(cfg, panel, reload_in_worker=rb.n_jobs > 1)
    extras: dict = {"periods_per_year": ppy}
    grid_spec = _resolve_grid(cfg)
    if (want_grid or want_wf) and grid_spec is None:
        raise CliError("this command needs `strategy.grid` in the config (a dict of param -> list of values, or `auto`)", EXIT_CONFIG)
    ledger = out / "_trials.jsonl"

    # --- causality (mandatory)
    caus = None
    leak = False
    if cfg.causality_check and not no_causality:
        rep = check_causality(lambda: build_strategy(cfg), panel, cfg.execution, cfg.initial_capital)
        caus = rep.to_dict()
        leak = not rep.ok
        print(rep.summary(), file=sys.stderr if leak else sys.stdout)
        extras["causality"] = caus

    # --- grid
    grid = None
    best_params = None
    if grid_spec is not None:
        grid = run_grid(run_fn, grid_spec, rb.objective, rb.n_jobs, seed, periods_per_year=ppy)
        best_params = grid.best_params
        extras["grid"] = grid
    # --- single run (configured params, or the in-sample best for `optimize`)
    use_params = best_params if (use_best and best_params) else None
    res = run_fn(use_params) if use_params else run_strategy(strat, panel, cfg)

    # --- walk-forward
    wf_cfg = rb.walkforward
    if want_wf and wf_cfg is None:
        raise CliError("walkforward needs robustness.walkforward {is_len, oos_len, ...} in the config", EXIT_CONFIG)
    if wf_cfg is not None and grid_spec is not None and (want_wf or command == "run"):
        wf = walk_forward(run_fn, grid_spec, pd.DatetimeIndex(res.returns_daily.index), wf_cfg.is_len, wf_cfg.oos_len, wf_cfg.step,
                          wf_cfg.scheme, wf_cfg.purge, rb.objective, rb.n_jobs, seed, ppy, float(cfg.initial_capital))
        extras["walkforward"] = wf

    # --- ledger: every search counts (append-only, never delete runs/_trials.jsonl)
    n_search = grid.n_trials if grid is not None else 1
    if command != "report":                      # regenerating a report is not a new trial
        trial_ledger_append(ledger, {"command": command, "strategy": strat.name, "config_hash": h, "n_trials": n_search,
                                     "objective": rb.objective, "grid": grid_spec, "data_fingerprint": panel.meta.get("fingerprint"),
                                     "seed": cfg.seed, "git_sha": _git(["rev-parse", "--short", "HEAD"]), "ts": run_stamp()})
    extras["n_trials"] = max(count_trials(ledger, strat.name), n_search)   # honest N: every earlier search of this strategy counts
    extras["data_quality"] = {s_: {**q.to_dict(), "ok": q.ok} for s_, q in panel.quality.items()}

    # --- report
    if run_dir is None:
        run_dir = make_run_dir(out, strat.name, h)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.resolved.yaml").write_text(yaml.safe_dump(resolved_dict(cfg), sort_keys=False))
    (run_dir / "data_quality.json").write_text(json.dumps(extras["data_quality"], indent=2, default=str))
    (run_dir / "env.json").write_text(json.dumps({**_env(), "seed": cfg.seed, "config_hash": h, "command": command,
                                                  "data_fingerprint": panel.meta.get("fingerprint")}, indent=2))
    if caus is not None:
        (run_dir / "causality.json").write_text(json.dumps(caus, indent=2))
    if best_params is not None:
        (run_dir / "best_params.json").write_text(json.dumps({"best_params": best_params, "objective": rb.objective,
                                                              "in_sample": True, "n_trials": grid.n_trials}, indent=2, default=float))
    build_run_report(run_dir, res, panel, cfg, run_fn, extras)
    update_latest(run_dir)
    return run_dir, (EXIT_LEAK if leak else EXIT_OK)


def _print_run(run_dir: Path) -> None:
    print(f"run dir: {run_dir}")
    sm = run_dir / "summary.md"
    if sm.exists():
        txt = sm.read_text()
        head = [ln for ln in txt.split("## Headline")[0].splitlines() if ln.startswith("- ") and ln.split(":")[0] in ("- strategy", "- params")]
        tail = "## Integrity" + txt.split("## Integrity", 1)[1].split("## Files")[0] if "## Integrity" in txt else ""
        print("\n".join(head) + "\n" + tail.rstrip())
    print(f"\nread first: {run_dir}/summary.md   (runs/LATEST -> {run_dir.name})")


def _out_root(a) -> Path:
    return Path(a.out_dir) if getattr(a, "out_dir", None) else project_root() / "runs"


def cmd_run(a) -> int:
    cfg = _load(a)
    run_dir, code = _execute(cfg, _out_root(a), want_grid=False, want_wf=False, no_causality=a.no_causality)
    _print_run(run_dir)
    if code == EXIT_LEAK:
        print("LEAK DETECTED: causality check failed; results are invalid.", file=sys.stderr)
    return code


def cmd_optimize(a) -> int:
    cfg = _load(a)
    if a.n_jobs:
        cfg.robustness.n_jobs = a.n_jobs
    run_dir, code = _execute(cfg, _out_root(a), want_grid=True, want_wf=False, no_causality=a.no_causality, use_best=True, command="optimize")
    _print_run(run_dir)
    print("NOTE: this report is the IN-SAMPLE best configuration of the grid; judge it by DSR/PBO/plateau, not by its Sharpe.")
    return code


def cmd_walkforward(a) -> int:
    cfg = _load(a)
    if a.n_jobs:
        cfg.robustness.n_jobs = a.n_jobs
    run_dir, code = _execute(cfg, _out_root(a), want_grid=True, want_wf=True, no_causality=a.no_causality, command="walkforward")
    _print_run(run_dir)
    return code


def cmd_report(a) -> int:
    """Regenerate every artifact of an existing run dir by re-running its config.resolved.yaml (deterministic)."""
    d = Path(a.run_dir).resolve()
    cfgp = d / "config.resolved.yaml"
    if not cfgp.exists():
        raise CliError(f"{cfgp} not found", EXIT_CONFIG)
    a.config = str(cfgp)
    cfg = _load(a)
    old = {}
    envp = d / "env.json"
    if envp.exists():
        old = json.loads(envp.read_text())
    run_dir, code = _execute(cfg, d.parent, want_grid=False, want_wf=False, run_dir=d, command="report")
    new_fp = json.loads((d / "env.json").read_text()).get("data_fingerprint")
    if old.get("data_fingerprint") and new_fp != old["data_fingerprint"]:
        print(f"[warn] data fingerprint changed since the original run ({old['data_fingerprint']} -> {new_fp})", file=sys.stderr)
    _print_run(run_dir)
    return code


def cmd_compare(a) -> int:
    from .report import build_compare_report

    out = Path(a.out_dir) if a.out_dir else project_root() / "runs" / f"compare_{run_stamp()}"
    build_compare_report([Path(p) for p in a.run_dirs], out)
    print(f"compare report: {out}/compare.html, {out}/compare.md")
    return 0


def cmd_list_strategies(a) -> int:
    for n, c in list_strategies().items():
        print(f"{n:24s} {c.mode:7s} {c.description}")
    return 0


def cmd_list_sources(a) -> int:
    print("\n".join(list_sources()))
    return 0


def cmd_describe(a) -> int:
    cls = get_strategy(a.strategy)
    print(f"{cls.name} [{cls.mode}]\n{cls.description}\nparams schema:")
    print(json.dumps(cls.Params.model_json_schema().get("properties", {}), indent=2, default=str))
    return 0


def cmd_check_causality(a) -> int:
    cfg = load_config(a.config)
    panel = load_panel(cfg.data)
    rep = check_causality(lambda: build_strategy(cfg), panel, cfg.execution, cfg.initial_capital, max_bars=a.max_bars)
    print(rep.summary())
    if cfg.strategy.name and not a.skip_engine:
        d = engine_delay_check(panel.head(min(len(panel.index), 8000)))
        print(f"engine delay sanity: {'ok' if d['ok'] else 'FAIL'} (oracle Sharpe: unsafe {d['sharpe_unsafe']:.1f}, next_open {d['sharpe_next_open']:.1f}, next_close {d['sharpe_next_close']:.1f})")
        if not d["ok"]:
            return EXIT_LEAK
    return EXIT_OK if rep.ok else EXIT_LEAK


def cmd_validate_data(a) -> int:
    cfg = load_config(a.config)
    panel = load_panel(cfg.data)
    bad = 0
    for s, q in panel.quality.items():
        print(f"{s}: {q.n_bars} bars, {'OK' if q.ok else 'ERRORS'}")
        for i in q.issues:
            print(f"  [{i['severity']}] {i['code']} x{i['count']} {i['detail']}")
        bad += 0 if q.ok else 1
    return 1 if bad else 0


def cmd_fetch_data(a) -> int:
    from .data.sources import get_source

    cfg = load_config(a.config)
    d = cfg.data
    out = Path(a.out_dir) if a.out_dir else project_root() / "data_store" / d.source
    out.mkdir(parents=True, exist_ok=True)
    src = get_source(d.source)
    for s in d.symbols:
        opts = dict(d.options)
        if d.source == "databento":
            opts["max_cost_usd"] = a.max_cost_usd
            c = src.estimate_cost(s, d.start, d.end, d.freq, **{k: v for k, v in opts.items() if k in ("dataset", "stype_in", "schema")})
            print(f"{s}: estimated cost ${c:.4f} (limit ${a.max_cost_usd})")
            if a.dry_run:
                continue
        df = src.load(s, d.start, d.end, d.base_freq or d.freq, adjusted=d.adjusted, **opts)
        p = out / f"{s.replace('/', '_')}_{d.base_freq or d.freq}.parquet"
        df.to_parquet(p)
        print(f"{s}: {len(df)} bars -> {p}")
    return 0


_TEMPLATE_VEC = '''from tradelab.strategy import Params, Strategy, grid, register


class {cls}Params(Params):
    n: int = grid(20, low=5, high=60, step=5)


@register
class {cls}(Strategy):
    name = "{name}"
    mode = "vector"
    Params = {cls}Params
    description = "TODO"

    def signals(self, data):
        close = data.field("close")
        return (close > close.rolling(self.params.n).mean()).astype(float)   # decided at close t; engine delays fill
'''
_TEMPLATE_EVT = '''from tradelab.strategy import Order, Params, Strategy, register


class {cls}Params(Params):
    risk_pct: float = 0.005


@register
class {cls}(Strategy):
    name = "{name}"
    mode = "event"
    Params = {cls}Params
    description = "TODO"

    def prepare(self, data):
        b = data[data.primary]
        return {{"sma": b["close"].rolling(20).mean()}}          # causal features only

    def on_bar(self, ctx):
        if ctx.position == 0 and ctx.close > ctx.f("sma"):
            return Order("buy", risk_pct=self.params.risk_pct, stop=ctx.close - 10 * ctx.spec.tick_size)
'''


def cmd_init_strategy(a) -> int:
    cls = "".join(w.capitalize() for w in a.name.split("_"))
    p = project_root() / "strategies" / f"{a.name}.py"
    if p.exists():
        print(f"{p} exists", file=sys.stderr)
        return 1
    p.write_text((_TEMPLATE_EVT if a.mode == "event" else _TEMPLATE_VEC).format(cls=cls, name=a.name))
    print(f"wrote {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tradelab", description="tradelab backtesting framework")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="run a backtest from a YAML config and write a run dir")
    p.add_argument("config")
    p.add_argument("--out-dir")
    p.add_argument("--no-causality", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.set_defaults(fn=cmd_run)
    for nm, fn_, hlp in (("optimize", cmd_optimize, "grid search (strategy.grid) + DSR/PBO + heatmaps; appends to runs/_trials.jsonl"),
                         ("walkforward", cmd_walkforward, "walk-forward (strategy.grid + robustness.walkforward): stitched OOS, per-fold params")):
        p = sub.add_parser(nm, help=hlp)
        p.add_argument("config")
        p.add_argument("--out-dir")
        p.add_argument("--n-jobs", type=int, default=0)
        p.add_argument("--no-causality", action="store_true")
        p.add_argument("--refresh", action="store_true")
        p.set_defaults(fn=fn_)
    p = sub.add_parser("report", help="regenerate all artifacts of a run dir from its config.resolved.yaml")
    p.add_argument("run_dir")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("compare", help="compare.html/compare.md for several run dirs")
    p.add_argument("run_dirs", nargs="+")
    p.add_argument("--out-dir")
    p.set_defaults(fn=cmd_compare)
    sub.add_parser("list-strategies").set_defaults(fn=cmd_list_strategies)
    sub.add_parser("list-sources").set_defaults(fn=cmd_list_sources)
    p = sub.add_parser("describe")
    p.add_argument("strategy")
    p.set_defaults(fn=cmd_describe)
    p = sub.add_parser("check-causality", help="prefix-invariance + future-poison leakage test")
    p.add_argument("config")
    p.add_argument("--max-bars", type=int, default=20000)
    p.add_argument("--skip-engine", action="store_true")
    p.set_defaults(fn=cmd_check_causality)
    p = sub.add_parser("validate-data")
    p.add_argument("config")
    p.set_defaults(fn=cmd_validate_data)
    p = sub.add_parser("fetch-data", help="download/cache data defined in a config (databento: cost-checked)")
    p.add_argument("config")
    p.add_argument("--out-dir")
    p.add_argument("--max-cost-usd", type=float, default=5.0)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_fetch_data)
    p = sub.add_parser("init-strategy")
    p.add_argument("name")
    p.add_argument("--mode", choices=["vector", "event"], default="vector")
    p.set_defaults(fn=cmd_init_strategy)
    a = ap.parse_args(argv)
    try:
        return int(a.fn(a) or 0)
    except CliError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    raise SystemExit(main())
