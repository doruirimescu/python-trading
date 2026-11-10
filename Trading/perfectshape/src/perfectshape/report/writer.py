"""Run outputs: results.csv, results.json, summary.md, report.html (self-contained, no network)."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from perfectshape.evaluate import Result
from perfectshape.pipeline import ScanOutput
from perfectshape.shapes import get_shape, linear_fit, range_band, to_space

MAX_CHART_POINTS = 400

METRIC_ORDER = {
    "uptrend": ["annual_return", "r2", "adverse_ratio"],
    "downtrend": ["annual_return", "r2", "adverse_ratio"],
    "range": ["harvest", "trades_per_year", "coverage", "per_trade", "worst_against", "swing_up", "swing_down",
              "band_pos", "drift_ratio"],
}


METRIC_LABEL = {"swing_up": "bottom→top", "swing_down": "top→bottom", "harvest": "harvest/yr",
                "trades_per_year": "trades/yr", "per_trade": "per trade", "band_pos": "now in band",
                "coverage": "repeat", "worst_against": "worst against"}


def _fmt_leg(members: list[str], weights: list[float]) -> str:
    return " + ".join(f"{w:.0%} {m}" for m, w in sorted(zip(members, weights), key=lambda x: -x[1]))


def _fmt_members(r: Result) -> str:
    b = r.basket
    if b.is_ratio:
        return f"({' + '.join(b.members)}) / ({' + '.join(b.den_members)})"
    return _fmt_leg(b.members, b.weights)


def _years(bars: int, ppy: int) -> float:
    return bars / ppy


def write_run(out: ScanOutput, root: str | Path | None = None) -> Path:
    cfg = out.cfg
    stamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    digest = hashlib.sha256(cfg.model_dump_json().encode()).hexdigest()[:8]
    run_dir = Path(root or cfg.output.dir) / f"{stamp}_{cfg.name}_{digest}"
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = _rows(out)
    _write_csv(run_dir / "results.csv", rows)
    payload = _payload(out, rows)
    (run_dir / "results.json").write_text(json.dumps(payload, indent=1, default=float), encoding="utf-8")
    (run_dir / "summary.md").write_text(_summary_md(out, rows), encoding="utf-8")
    (run_dir / "config.resolved.json").write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    if cfg.output.html:
        from perfectshape.report.html import render_html
        (run_dir / "report.html").write_text(render_html(payload), encoding="utf-8")
    latest = run_dir.parent / "LATEST"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(run_dir.name)
    return run_dir


def _rows(out: ScanOutput) -> list[dict]:
    ppy = out.cfg.scoring.periods_per_year
    rows = []
    for shape, results in out.ranked.items():
        for rank, r in enumerate(results, 1):
            row = {
                "shape": shape, "rank": rank, "members": " ".join(r.basket.members),
                "weights": " ".join(f"{w:.4f}" for w in r.basket.weights),
                "weights_now": " ".join(f"{w:.4f}" for w in r.weights_now),
                "names": " | ".join(out.universe.name(m) for m in r.basket.members),
                "den_members": " ".join(r.basket.den_members),
                "den_weights": " ".join(f"{w:.4f}" for w in r.basket.den_weights),
                "den_weights_now": " ".join(f"{w:.4f}" for w in r.den_weights_now),
                "den_names": " | ".join(out.universe.name(m) for m in r.basket.den_members),
                "duration_bars": r.duration, "duration_years": round(_years(r.duration, ppy), 2),
                "score": round(r.score, 4), "score_window": r.ref_window, "fit_window": r.basket.fit_window, "alive": r.alive,
                "holdout_return": round(r.holdout_return, 4),
            }
            row.update({k: round(v, 4) for k, v in r.metrics.items()})
            row.update({f"score_{L}": round(v, 3) for L, v in r.window_scores.items()})
            rows.append(row)
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _chart(out: ScanOutput, r: Result, shape_name: str) -> dict:
    """Curve + overlay (fitted line or band over the duration window) for the HTML chart."""
    space = out.cfg.scoring.space
    dates = out.panel.dates[r.chart_start:]
    curve = r.curve
    ref = r.ref_window or r.duration or r.basket.fit_window
    off = r.fit_end - ref - r.chart_start
    seg = curve[off:off + ref]
    overlay: dict = {"from": int(off), "to": int(off + ref)}
    if shape_name == "range":
        Y = to_space(seg, space)
        q = out.cfg.scoring.range_band_pct
        lo, mid, hi = range_band(Y, q)
        inv = np.exp if space == "log" else (lambda x: x)
        overlay.update(kind="band", lo=float(inv(lo)), mid=float(inv(mid)), hi=float(inv(hi)), pct=q)
    else:
        a, b, _, _ = linear_fit(to_space(seg, space)[:, None])
        n = len(seg)
        line = a[0] + b[0] * np.linspace(0, 1, n)
        line = np.exp(line) if space == "log" else line
        overlay.update(kind="line", y0=float(line[0]), y1=float(line[-1]))
    # downsample long curves for the page, always keeping the window/holdout boundaries and the last bar
    n = len(curve)
    hold = int(r.fit_end - r.chart_start)
    stride = max(1, int(np.ceil(n / MAX_CHART_POINTS)))
    keep = np.unique(np.r_[np.arange(0, n, stride), [off, off + ref - 1, hold - 1, min(hold, n - 1), n - 1]])
    keep = keep[(keep >= 0) & (keep < n)]
    remap = lambda i: int(np.searchsorted(keep, i))
    overlay["from"], overlay["to"] = remap(overlay["from"]), remap(overlay["to"] - 1) + 1
    return {
        "dates": [str(d) for d in dates[keep]],
        "values": [round(float(v), 4) for v in curve[keep]],
        "holdout_from": remap(hold),
        "overlay": overlay,
        "log": space == "log",
    }


def _payload(out: ScanOutput, rows: list[dict]) -> dict:
    cfg = out.cfg
    shapes = {}
    for shape, results in out.ranked.items():
        items = []
        for rank, r in enumerate(results, 1):
            items.append({
                "rank": rank,
                "members": [{"ticker": m, "name": out.universe.name(m), "sector": out.universe.sector(m),
                             "weight": w, "weight_now": wn}
                            for m, w, wn in zip(r.basket.members, r.basket.weights, r.weights_now)],
                "den_members": [{"ticker": m, "name": out.universe.name(m), "sector": out.universe.sector(m),
                                 "weight": w, "weight_now": wn}
                                for m, w, wn in zip(r.basket.den_members, r.basket.den_weights,
                                                    r.den_weights_now)],
                "duration": r.duration, "score": r.score, "ref_window": r.ref_window,
                "fit_window": r.basket.fit_window,
                "alive": r.alive, "holdout_return": r.holdout_return, "metrics": r.metrics,
                "window_scores": {str(k): v for k, v in r.window_scores.items()},
                "chart": _chart(out, r, shape),
            })
        shapes[shape] = {"candidates": out.n_candidates[shape], "items": items,
                         "metric_order": METRIC_ORDER.get(shape, [])}
    return {
        "name": cfg.name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "panel": {"bars": out.panel.n_bars, "symbols": len(out.panel.symbols),
                  "requested": len(out.universe.tickers),
                  "start": str(out.panel.dates[0]), "end": str(out.panel.dates[-1]),
                  "fit_end": str(out.panel.dates[out.fit_end - 1])},
        "search": cfg.search.model_dump(), "scoring": cfg.scoring.model_dump(), "ratio": cfg.ratio.model_dump(),
        "universe_lists": cfg.universe.lists, "seconds": round(out.seconds, 1),
        "shapes": shapes,
    }


def _summary_md(out: ScanOutput, rows: list[dict]) -> str:
    cfg, p = out.cfg, out.panel
    ppy = cfg.scoring.periods_per_year
    lines = [
        f"# perfectshape scan: {cfg.name}", "",
        "## Meta",
        f"- universe: {', '.join(cfg.universe.lists) or 'inline'} ({len(out.universe.tickers)} requested, "
        f"{len(p.symbols)} with data)",
        f"- bars: {p.n_bars} ({p.dates[0]} .. {p.dates[-1]})",
        f"- fit end: {p.dates[out.fit_end - 1]} (holdout {cfg.search.holdout_bars} bars after it)",
        f"- windows: {cfg.search.windows}",
        _basket_desc(cfg),
        f"- threshold: {cfg.scoring.threshold}, space: {cfg.scoring.space}, runtime: {out.seconds:.1f}s", "",
    ]
    for shape, results in out.ranked.items():
        lines += [f"## {shape} ({len(results)} ranked of {out.n_candidates[shape]} candidates)", ""]
        if not results:
            lines += ["- none held the shape over any window", ""]
            continue
        mk = METRIC_ORDER.get(shape, [])
        lines.append("| # | basket | held | score | " + " | ".join(METRIC_LABEL.get(k, k) for k in mk)
                     + " | holdout | alive |")
        lines.append("|---|---|---|---|" + "---|" * len(mk) + "---|---|")
        for i, r in enumerate(results, 1):
            ms = " | ".join(_fmt_metric(k, r.metrics.get(k, float('nan'))) for k in mk)
            scored = (f", scored on {_years(r.ref_window, ppy):.1f}y" if r.ref_window and r.ref_window != r.duration
                      else "")
            lines.append(f"| {i} | {_fmt_members(r)} | {r.duration} bars ({_years(r.duration, ppy):.1f}y{scored}) | "
                         f"{r.score:.3f} | {ms} | {r.holdout_return:+.1%} | {'yes' if r.alive else 'NO'} |")
        lines.append("")
    lines += [
        "## Caveats",
        "- In-sample search over many instruments and combinations: some shapes are coincidence. "
        "Trust baskets that are long-lived, alive through the holdout, and economically sensible.",
        "- Universe is today's constituents (survivorship bias).",
        "- Weights are capital weights at the fit-window start, held as fixed shares (no rebalancing); "
        "`weights_now` in results.csv is the drifted allocation at the last bar.",
        *(["- Ratio mode: each leg is equal-weight at the fit-window start; value = numerator / denominator. "
            "Trends are oriented so the numerator outperforms (a falling A/B is listed as a rising B/A)."]
          if cfg.search.mode == "ratio" else []),
        "",
        "## Files",
        "- results.csv, results.json, report.html, config.resolved.json",
    ]
    return "\n".join(lines) + "\n"


def _basket_desc(cfg) -> str:
    if cfg.search.mode == "ratio":
        r = cfg.ratio
        return (f"- basket ratios: {r.k_num} vs {r.k_den} instruments, equal weight per leg, "
                f"{'overlap allowed' if r.allow_overlap else 'disjoint legs'}")
    s = cfg.search
    return (f"- basket: max {s.max_assets} assets, {'long-only' if s.long_only else 'long/short'}, "
            f"max weight {s.max_weight:.0%}")


def _fmt_metric(k: str, v: float) -> str:
    if k in ("annual_return", "swing_up", "harvest", "per_trade"):
        return f"{v:+.1%}"
    if k in ("band_pos", "coverage"):
        return f"{v:.0%}"
    if k == "trades_per_year":
        return f"{v:.1f}"
    if k in ("swing_down", "worst_against"):
        return f"{-v:+.1%}"
    if k == "height":
        return f"{v:.1%}"
    if k == "swings":
        return f"{v:.0f}"
    return f"{v:.2f}"


__all__ = ["write_run", "get_shape"]
