"""Compare several run directories: compare.html + compare.md."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import plots as P
from .run_dir import read_json
from .tearsheet import CSS, fig, num, pct

KEYS = [("cagr", "CAGR", "pct"), ("sharpe", "Sharpe", "num"), ("sortino", "Sortino", "num"), ("max_drawdown", "Max DD", "pct"),
        ("calmar", "Calmar", "num"), ("annual_vol", "Vol", "pct"), ("total_return", "Total return", "pct")]
TKEYS = [("n_trades", "Trades", "num0"), ("hit_rate", "Hit rate", "pct"), ("profit_factor", "PF", "num"), ("expectancy", "Expectancy", "num")]
RKEYS = [("expectancy_r", "Exp R", "num"), ("sqn", "SQN", "num")]


def _fmt(v, kind):
    return pct(v) if kind == "pct" else (num(v, 0) if kind == "num0" else num(v))


def _label(d: Path, m: dict) -> str:
    s = (m.get("meta") or {}).get("strategy", "run")
    return f"{s} [{d.name.split('_')[-1][:8]}]" if "_" in d.name else d.name


def load_run(d: Path) -> dict:
    m = read_json(d / "metrics.json")
    rob = read_json(d / "robustness.json") if (d / "robustness.json").exists() else {}
    r = pd.read_csv(d / "returns_daily.csv", index_col=0, parse_dates=True).iloc[:, 0] if (d / "returns_daily.csv").exists() else pd.Series(dtype=float)
    return {"dir": d, "metrics": m, "rob": rob, "returns": r, "label": _label(d, m)}


def build_compare_report(run_dirs: list[str | Path], out_dir: str | Path) -> Path:
    """Write ``compare.html`` and ``compare.md`` into ``out_dir`` (created). Returns ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs = [load_run(Path(d)) for d in run_dirs]
    labels, seen = [], {}
    for r in runs:
        seen[r["label"]] = seen.get(r["label"], 0) + 1
        labels.append(r["label"] if seen[r["label"]] == 1 else f'{r["label"]}#{seen[r["label"]]}')
    rows = []
    for lab, r in zip(labels, runs):
        m = r["metrics"]
        row = {"run": lab}
        for k, name, kind in KEYS:
            row[name] = _fmt(m.get(k), kind)
        for k, name, kind in TKEYS:
            row[name] = _fmt(m.get("trades", {}).get(k), kind)
        for k, name, kind in RKEYS:
            row[name] = _fmt(m.get("rmultiple", {}).get(k), kind)
        row["PSR(0)"] = num(r["rob"].get("psr", {}).get("psr0"), 3)
        row["DSR"] = num(r["rob"].get("psr", {}).get("dsr"), 3)
        row["Verdict"] = r["rob"].get("verdict", {}).get("overall", "n/a")
        rows.append(row)
    tbl = pd.DataFrame(rows)
    # md
    cols = list(tbl.columns)
    md = ["# Run comparison", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(v) for v in row) + " |" for row in tbl.to_numpy()]
    md += ["", "## Runs"] + [f"- {lab}: {r['dir']}" for lab, r in zip(labels, runs)]
    (out / "compare.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    # html
    f1 = go.Figure()
    for i, (lab, r) in enumerate(zip(labels, runs)):
        s = r["returns"]
        if len(s):
            f1.add_trace(go.Scatter(x=s.index, y=(1 + s).cumprod(), name=lab, line=dict(color=P.PALETTE[i % 8], width=1.8)))
    f1.update_layout(**P.base_layout("Growth of 1 (log scale)", 440))
    f1.update_yaxes(type="log", title_text="Growth of 1 (log)")
    frames = {lab: r["returns"] for lab, r in zip(labels, runs) if len(r["returns"])}
    corr_html = ""
    if len(frames) >= 2:
        c = pd.DataFrame(frames).corr()
        f2 = go.Figure(go.Heatmap(z=c.to_numpy(), x=list(c.columns), y=list(c.index), zmin=-1, zmax=1, zmid=0, colorscale=P.DIVERGING,
                                  text=np.round(c.to_numpy(), 2), texttemplate="%{text}"))
        f2.update_layout(**P.base_layout("Daily return correlation", 360, hovermode="closest"))
        corr_html = fig(f2)
    dd = go.Figure()
    for i, (lab, s) in enumerate(frames.items()):
        cur = (1 + s).cumprod()
        dd.add_trace(go.Scatter(x=s.index, y=(cur / cur.cummax() - 1) * 100, name=lab, line=dict(color=P.PALETTE[i % 8], width=1.2)))
    dd.update_layout(**P.base_layout("Drawdown (%)", 320))
    dd.update_yaxes(title_text="Drawdown (%)")
    from plotly.offline import get_plotlyjs
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Run comparison</title><style>{CSS}</style><script>{get_plotlyjs()}</script></head><body><main><h1>Run comparison</h1>'
            f'{tbl.to_html(classes="tbl", index=False, border=0, escape=True)}{fig(f1)}{fig(dd)}{corr_html}</main></body></html>')
    (out / "compare.html").write_text(page, encoding="utf-8")
    return out
