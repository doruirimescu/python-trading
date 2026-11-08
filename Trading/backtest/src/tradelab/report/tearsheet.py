"""Self-contained HTML tearsheet assembled from plug-in ``Section`` objects.

Add a section::

    @register_section
    class MySection(Section):
        id, title, order = "my", "My section", 55
        def render(self, ctx): return "<p>...</p>"   # return "" to skip

plotly.js is embedded once inline (works offline).
"""
from __future__ import annotations

import html
import traceback
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from tradelab.analytics.metrics import daily_returns, trade_col
from tradelab.analytics.rmultiple import r_equity, r_series

from . import plots as P

# ------------------------------------------------------------------ context & registry


@dataclass
class ReportContext:
    result: Any
    metrics: dict
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)      # periodic + R tables
    robustness: dict = field(default_factory=dict)                     # JSON-able dict
    objs: dict[str, Any] = field(default_factory=dict)                 # non-JSON robustness objects (grid, bootstrap samples...)
    panel: Any = None
    cfg: Any = None
    extras: dict = field(default_factory=dict)
    title: str = "Backtest tearsheet"


class Section:
    id: str = "section"
    title: str = "Section"
    order: int = 100

    def render(self, ctx: ReportContext) -> str:  # pragma: no cover - interface
        raise NotImplementedError


SECTION_REGISTRY: dict[str, Section] = {}


def register_section(cls_or_obj: Any) -> Any:
    """Class decorator / function: instantiate and register a Section (replaces same id)."""
    obj = cls_or_obj() if isinstance(cls_or_obj, type) else cls_or_obj
    SECTION_REGISTRY[obj.id] = obj
    return cls_or_obj


# ------------------------------------------------------------------ formatting


def pct(v: Any, d: int = 1) -> str:
    return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v * 100:.{d}f}%"


def num(v: Any, d: int = 2) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    if isinstance(v, float) and np.isinf(v):
        return "inf"
    return f"{v:,.{d}f}"


def fig(f) -> str:
    return f'<div class="fig">{P.fig_html(f)}</div>'


def table_html(df: pd.DataFrame, fmt: dict[str, str] | None = None, max_rows: int = 40) -> str:
    if df is None or len(df) == 0:
        return '<p class="muted">no data</p>'
    d = df.head(max_rows).copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:,.4g}")
    return d.to_html(classes="tbl", border=0, escape=True, na_rep="")


def kpi(label: str, value: str, tone: str = "") -> str:
    return f'<div class="kpi {tone}"><div class="kv">{html.escape(value)}</div><div class="kl">{html.escape(label)}</div></div>'


# ------------------------------------------------------------------ sections


@register_section
class OverviewSection(Section):
    id, title, order = "overview", "Overview", 10

    def render(self, ctx: ReportContext) -> str:
        m, tr, rm = ctx.metrics, ctx.metrics.get("trades", {}), ctx.metrics.get("rmultiple", {})
        v = ctx.robustness.get("verdict", {}).get("overall", "n/a")
        psr0 = ctx.robustness.get("psr", {}).get("psr0")
        k = [
            kpi("CAGR", pct(m.get("cagr"))), kpi("Sharpe", num(m.get("sharpe"))), kpi("Sortino", num(m.get("sortino"))),
            kpi("Max drawdown", pct(m.get("max_drawdown")), "neg"), kpi("Calmar", num(m.get("calmar"))),
            kpi("Annual vol", pct(m.get("annual_vol"))), kpi("Trades", str(tr.get("n_trades", 0))),
            kpi("Hit rate", pct(tr.get("hit_rate"))), kpi("Profit factor", num(tr.get("profit_factor"))),
            kpi("Expectancy (R)", num(rm.get("expectancy_r"))), kpi("SQN", num(rm.get("sqn"))),
            kpi("PSR(0)", num(psr0, 3)), kpi("Verdict", str(v), {"green": "pos", "red": "neg", "amber": "warn"}.get(v, "")),
        ]
        meta = ctx.result.meta or {}
        mt = " &middot; ".join(f"{html.escape(str(a))}: <b>{html.escape(str(meta[a]))}</b>" for a in ("strategy", "freq", "mode", "seed") if a in meta)
        params = meta.get("params")
        pr = f'<p class="muted">params: <code>{html.escape(str(params))}</code></p>' if params else ""
        return f'<p class="muted">{mt}</p>{pr}<div class="kpis">{"".join(k)}</div>'


@register_section
class EquitySection(Section):
    id, title, order = "equity", "Equity and drawdown", 20

    def render(self, ctx: ReportContext) -> str:
        return fig(P.equity_fig(ctx.result))


@register_section
class ReturnsSection(Section):
    id, title, order = "returns", "Returns", 30

    def render(self, ctx: ReportContext) -> str:
        out = []
        t = ctx.tables
        if "month" in t:
            out.append(fig(P.monthly_heatmap(t["month"])))
        if "year" in t:
            out.append(fig(P.bar_fig(t["year"].index, t["year"]["return"] * 100, "Calendar-year return (%)", "Return (%)", text_fmt=".1f")))
        r = daily_returns(ctx.result)
        out.append(fig(P.hist_fig(r.to_numpy(), "Distribution of daily returns", "Daily return (%)", pct_x=True)))
        out.append(fig(P.rolling_fig(r)))
        if "weekday" in t:
            out.append(fig(P.bar_fig(t["weekday"].index, t["weekday"]["mean_daily"] * 1e4, "Mean daily return by weekday (bp)", "bp", text_fmt=".1f")))
        return "".join(out)


@register_section
class TradesSection(Section):
    id, title, order = "trades", "Trades and R-multiples", 40

    def render(self, ctx: ReportContext) -> str:
        tr = getattr(ctx.result, "trades", None)
        if tr is None or len(tr) == 0:
            return '<p class="muted">no trades</p>'
        out = []
        r = r_series(tr)
        if len(r):
            out.append(fig(P.hist_fig(r.to_numpy(), "R-multiple distribution (net)", "R", bins=30, vline=float(r.mean()),
                                      vline_label=f"mean {r.mean():.2f}R")))
            out.append(fig(P.line_fig(list(range(1, len(r) + 1)), {"cumulative R": r_equity(tr)}, "Cumulative R", "R", "trade #")))
        out.append(fig(P.mae_mfe_fig(tr)))
        t = ctx.tables
        if "by_entry_hour" in t:
            h = t["by_entry_hour"]
            out.append(fig(P.bar_fig(h.index, h["expectancy_r"], "Expectancy by entry hour (R)", "R per trade")))
        if "by_exit_reason" in t:
            h = t["by_exit_reason"]
            out.append(fig(P.bar_fig(h.index, h["total_r"], "Total R by exit reason", "R")) + table_html(h))
        if "by_trade_of_day" in t:
            h = t["by_trade_of_day"]
            out.append(fig(P.bar_fig(h.index, h["expectancy_r"], "Expectancy by trade # of the day (R)", "R per trade")))
        if "hour_of_day" in t:
            h = t["hour_of_day"]
            out.append(fig(P.bar_fig(h.index, h["pnl_sum"], "Bar P&L by hour of day (currency)", "currency", text_fmt=".0f")))
        return "".join(out)


@register_section
class RobustnessSection(Section):
    id, title, order = "robustness", "Robustness", 50

    def render(self, ctx: ReportContext) -> str:
        rb, o = ctx.robustness, ctx.objs
        out = []
        v = rb.get("verdict")
        if v:
            rows = "".join(f'<tr><td>{html.escape(c["check"])}</td><td>{num(c["value"], 3) if isinstance(c["value"], (int, float)) and not isinstance(c["value"], bool) else html.escape(str(c["value"]))}</td>'
                           f'<td>{html.escape(c["threshold"])}</td><td><span class="tl {c["status"]}">{c["status"]}</span></td></tr>' for c in v["checks"])
            out.append(f'<h3>Advisory verdict: <span class="tl {v["overall"]}">{v["overall"]}</span></h3>'
                       f'<table class="tbl"><tr><th>check</th><th>value</th><th>threshold</th><th>status</th></tr>{rows}</table>'
                       '<p class="muted">Advisory only: passing these checks does not prove an edge.</p>')
        ps = rb.get("psr")
        if ps:
            out.append(f'<p>PSR(0) = <b>{num(ps.get("psr0"), 3)}</b>; MinTRL = <b>{num(ps.get("min_trl_days"), 0)}</b> daily obs '
                       f'(have {ps.get("T")}); per-period SR {num(ps.get("sr_per_period"), 4)}, skew {num(ps.get("skew"))}, kurtosis {num(ps.get("kurt"))}.'
                       + (f' DSR = <b>{num(ps["dsr"], 3)}</b> over {ps["n_trials"]} trials.' if ps.get("dsr") is not None else "") + "</p>")
        bs = o.get("bootstrap")
        if bs is not None and len(bs.samples):
            out.append(fig(P.hist_fig(bs.samples["sharpe"], "Block-bootstrap Sharpe distribution", "Sharpe (annualised)",
                                      vline=bs.summary.get("observed_sharpe"), vline_label="observed")))
            out.append(fig(P.hist_fig(bs.samples["max_drawdown"], "Block-bootstrap max drawdown", "Max drawdown (%)", pct_x=True)))
        mc = o.get("monte_carlo")
        if mc is not None and len(mc.samples):
            out.append(fig(P.hist_fig(mc.samples["max_drawdown"], "Trade-resample Monte Carlo: max drawdown", "Max drawdown (%)", pct_x=True))
                       + f'<p>Risk of ruin (equity &le; {mc.summary["ruin_level"]:.0%} of initial): <b>{pct(mc.summary["risk_of_ruin"])}</b></p>')
        cs = o.get("cost_table")
        if cs is not None:
            m = cs[cs.cost_mult.notna()]
            out.append(fig(P.bar_fig([f"{x:g}x" for x in m.cost_mult], m["total_return"] * 100, "Total return vs cost multiplier (%)", "Total return (%)", text_fmt=".1f"))
                       + table_html(cs) + (f'<p>Break-even cost multiplier: <b>{num(rb.get("cost_sensitivity", {}).get("breakeven_cost_mult"))}</b>x</p>'))
        rg = o.get("regimes")
        if rg:
            for name in ("volatility", "trend", "year"):
                if name in rg:
                    t = rg[name]
                    out.append(fig(P.bar_fig(t.index, t["sharpe"].astype(float), f"Sharpe by {name} regime", "Sharpe (annualised)")))
        return "".join(out) or '<p class="muted">no robustness results</p>'


@register_section
class GridSection(Section):
    id, title, order = "grid", "Parameter grid and PBO", 60

    def render(self, ctx: ReportContext) -> str:
        g = ctx.objs.get("grid")
        out = []
        if g is not None and len(g.table):
            names = [p for p in g.param_names if g.table[p].nunique() > 1]
            from tradelab.robustness.grid import heatmap_data
            if len(names) >= 2:
                out.append(fig(P.heatmap_fig(heatmap_data(g.table, names[0], names[1]), f"{g.objective} by parameters (max over others)", names[0], names[1], g.objective)))
            elif len(names) == 1:
                t = g.table.sort_values(names[0])
                out.append(fig(P.line_fig(t[names[0]].astype(str), {g.objective: t["objective"]}, f"{g.objective} vs {names[0]}", g.objective, names[0])))
            out.append(f'<p>Best: <code>{html.escape(str(g.best_params))}</code> ({g.objective} = {num(g.best_score, 3)}); trials = {g.n_trials}; plateau score = <b>{num(g.plateau_score, 2)}</b></p>')
        pbo = ctx.robustness.get("pbo")
        if pbo and pbo.get("pbo") is not None:
            lg = ctx.objs.get("pbo_logits")
            if lg is not None:
                out.append(fig(P.hist_fig(lg, "CSCV logit distribution (lambda <= 0 means overfit)", "lambda", vline=0.0, vline_label="0")))
            out.append(f'<p>PBO = <b>{num(pbo["pbo"], 3)}</b> over {pbo["n_combos"]} combinations, {pbo["n_configs"]} configurations.</p>')
        return "".join(out)


@register_section
class WalkForwardSection(Section):
    id, title, order = "walkforward", "Walk-forward", 70

    def render(self, ctx: ReportContext) -> str:
        wf = ctx.objs.get("walkforward")
        if wf is None or not len(wf.folds):
            return ""
        eq = wf.oos_equity
        out = [fig(P.line_fig(P._naive(eq.index), {"stitched OOS equity": eq}, "Stitched out-of-sample equity", "Account value (log)", log_y=True))]
        df = pd.DataFrame([{k: f[k] for k in ("fold", "is_start_date", "is_end_date", "oos_start_date", "oos_end_date", "params", "is_objective", "oos_objective")} for f in wf.folds])
        out.append(table_html(df))
        out.append(f'<p>WF efficiency (OOS / IS objective) = <b>{num(wf.efficiency, 2)}</b>; stitched OOS Sharpe = <b>{num(wf.oos_sharpe, 2)}</b>; scheme = {wf.scheme}.</p>')
        return "".join(out)


def _get_bars(panel: Any, symbol: str) -> pd.DataFrame | None:
    if panel is None:
        return None
    if isinstance(panel, pd.DataFrame):
        return panel
    for getter in (lambda: panel.bars[symbol], lambda: panel[symbol], lambda: panel.data[symbol], lambda: panel.frames[symbol]):
        try:
            d = getter()
            if isinstance(d, pd.DataFrame) and {"open", "high", "low", "close"} <= set(d.columns):
                return d
        except Exception:
            continue
    return None


@register_section
class TradeViewerSection(Section):
    id, title, order = "trade_viewer", "Trade viewer (best / worst / sample)", 80

    def render(self, ctx: ReportContext) -> str:
        tr = getattr(ctx.result, "trades", None)
        if tr is None or len(tr) == 0 or ctx.panel is None:
            return ""
        t = tr.reset_index(drop=True)
        key = trade_col(t, "R_net")
        key = pd.Series(key, dtype=float) if key is not None else pd.Series(trade_col(t, "net_pnl"), dtype=float)
        if key.isna().all():
            return ""
        n_each = int(((ctx.extras or {}).get("trade_viewer") or {}).get("n_each", 3))
        order = key.sort_values(kind="stable")
        best, worst = list(order.index[::-1][:n_each]), list(order.index[:n_each])
        rest = [i for i in t.index if i not in set(best) | set(worst)]
        rng = np.random.default_rng(int((ctx.result.meta or {}).get("seed", 42) or 42))
        samp = sorted(rng.choice(rest, min(4, len(rest)), replace=False).tolist()) if rest else []
        tz = (ctx.result.meta or {}).get("tz")
        cells = []
        for label, ids in (("best", best), ("worst", worst), ("sample", samp)):
            for i in ids:
                row = t.loc[i]
                bars = _get_bars(ctx.panel, str(row.get("symbol")))
                try:
                    f = P.candle_fig(bars, row, f"{label}: #{row.get('id', i)} {row.get('side', '')} R={key[i]:.2f}", tz=tz)
                except Exception:
                    f = None
                if f is not None:
                    cells.append(fig(f))
        if not cells:
            return '<p class="muted">panel provided no bars for the selected trades</p>'
        return f'<div class="grid2">{"".join(cells)}</div>'


# ------------------------------------------------------------------ page assembly

CSS = """
:root{--bg:#fff;--fg:#1b1f24;--muted:#5b6370;--card:#f3f4f6;--line:#d8dbe0;--pos:#0072B2;--neg:#D55E00;--warn:#E69F00}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--fg:#e6e8eb;--muted:#9aa3af;--card:#1e232a;--line:#313842;--pos:#56B4E9;--neg:#E8814A;--warn:#F0C040}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:16px}h1{font-size:22px;margin:8px 0 4px}h2{font-size:18px;border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:32px}
h3{font-size:15px}.muted{color:var(--muted)}code{background:var(--card);padding:1px 5px;border-radius:4px}
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;margin:12px 0}
.kpi{background:var(--card);border-radius:8px;padding:10px 12px}.kv{font-size:20px;font-weight:600}.kl{color:var(--muted);font-size:12px}
.kpi.pos .kv{color:var(--pos)}.kpi.neg .kv{color:var(--neg)}.kpi.warn .kv{color:var(--warn)}
.tbl{border-collapse:collapse;font-size:12px;margin:8px 0;display:block;overflow-x:auto}.tbl th,.tbl td{padding:3px 9px;border-bottom:1px solid var(--line);text-align:right}
.tbl th:first-child,.tbl td:first-child{text-align:left}
.tl{padding:1px 8px;border-radius:10px;font-weight:600;color:#000}.tl.green{background:#59c9a5}.tl.amber{background:#F0C040}.tl.red{background:#E8814A}.tl.na,.tl.n\\/a{background:#bbb}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:8px}.fig{min-width:0}
nav a{margin-right:12px;color:var(--pos);text-decoration:none}@media(max-width:560px){.grid2{grid-template-columns:1fr}}
"""


def render_tearsheet(ctx: ReportContext, sections: list[Section] | None = None) -> str:
    """Render all registered sections (a failing section shows its error instead of breaking the page)."""
    from plotly.offline import get_plotlyjs
    secs = sorted(sections or SECTION_REGISTRY.values(), key=lambda s: (s.order, s.id))
    body, nav = [], []
    for s in secs:
        try:
            h = s.render(ctx)
        except Exception as e:  # keep the report alive
            h = f'<p class="muted">section failed: {html.escape(repr(e))}</p><pre>{html.escape(traceback.format_exc()[-800:])}</pre>'
        if not h:
            continue
        nav.append(f'<a href="#{s.id}">{html.escape(s.title.split(" (")[0])}</a>')
        body.append(f'<section id="{s.id}"><h2>{html.escape(s.title)}</h2>{h}</section>')
    meta = ctx.result.meta or {}
    title = f'{meta.get("strategy", "backtest")} tearsheet'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style><script>{get_plotlyjs()}</script></head><body><main>'
            f'<h1>{html.escape(title)}</h1><nav>{"".join(nav)}</nav>{"".join(body)}</main></body></html>')
