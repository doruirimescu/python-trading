"""Plotly figure builders. Colour-blind-safe (Okabe-Ito), neutral transparent styling that reads on
light and dark pages, log-scale equity, units in every axis title."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BLUE, ORANGE, GREEN, VERMILLION = "#0072B2", "#E69F00", "#009E73", "#D55E00"
SKY, PURPLE, YELLOW, GREY = "#56B4E9", "#CC79A7", "#F0E442", "#8a8f98"
PALETTE = [BLUE, ORANGE, GREEN, VERMILLION, SKY, PURPLE, YELLOW, GREY]
POS, NEG = BLUE, VERMILLION
DIVERGING = [[0, VERMILLION], [0.5, "#f2f2f2"], [1, BLUE]]
_GRID = "rgba(128,128,128,0.22)"


def base_layout(title: str, height: int = 380, **kw: Any) -> dict:
    d = dict(
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=15)),
        height=height, margin=dict(l=56, r=20, t=48, b=44),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=12, color=GREY),
        xaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID, linecolor=_GRID),
        yaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID, linecolor=_GRID),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
        hovermode="x unified", colorway=PALETTE)
    d.update(kw)
    return d


def fig_html(fig: go.Figure) -> str:
    """Div without bundled JS (the page embeds plotly.js exactly once)."""
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displaylogo": False, "responsive": True, "displayModeBar": "hover"})


def _naive(idx: pd.Index) -> pd.Index:
    idx = pd.DatetimeIndex(idx)
    return idx.tz_localize(None) if idx.tz is not None else idx


def empty_fig(title: str, msg: str = "no data") -> go.Figure:
    f = go.Figure()
    f.update_layout(**base_layout(title, 240))
    f.add_annotation(text=msg, showarrow=False, font=dict(size=14, color=GREY), x=0.5, y=0.5, xref="paper", yref="paper")
    return f


def equity_fig(result: Any, max_points: int = 6000) -> go.Figure:
    """Log-scale equity (currency) with benchmark rebased to the same start, plus drawdown panel."""
    r = pd.Series(result.returns_daily, dtype=float).dropna()
    if r.empty:
        return empty_fig("Equity")
    cap = float(result.initial_capital)
    idx = _naive(r.index)
    curve = pd.Series(cap * (1 + r.to_numpy()).cumprod(), index=idx)
    dd = curve / curve.cummax().clip(lower=cap) - 1
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.04)
    eq = pd.Series(result.equity, dtype=float).dropna() if getattr(result, "equity", None) is not None else None
    if eq is not None and len(eq) > len(curve) * 1.5:  # intraday: show bar-level equity
        e = eq.iloc[:: max(1, len(eq) // max_points)]
        fig.add_trace(go.Scatter(x=_naive(e.index), y=e.to_numpy(), name="Strategy (bars)", line=dict(color=BLUE, width=1.4)), 1, 1)
    else:
        fig.add_trace(go.Scatter(x=curve.index, y=curve.to_numpy(), name="Strategy", line=dict(color=BLUE, width=1.8)), 1, 1)
    b = getattr(result, "benchmark_daily", None)
    if b is not None and len(b):
        bb = pd.Series(b, dtype=float).reindex(r.index).fillna(0.0)
        bc = pd.Series(cap * (1 + bb.to_numpy()).cumprod(), index=idx)
        fig.add_trace(go.Scatter(x=bc.index, y=bc.to_numpy(), name="Benchmark", line=dict(color=ORANGE, width=1.4, dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=dd.index, y=dd.to_numpy() * 100, name="Drawdown", fill="tozeroy", line=dict(color=VERMILLION, width=1),
                             fillcolor="rgba(213,94,0,0.30)"), 2, 1)
    fig.update_layout(**base_layout("Equity (log scale) and drawdown", 520))
    fig.update_yaxes(type="log", title_text="Account value (currency, log)", row=1, col=1, gridcolor=_GRID)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1, gridcolor=_GRID)
    fig.update_xaxes(gridcolor=_GRID)
    return fig


def monthly_heatmap(month_tbl: pd.DataFrame) -> go.Figure:
    if month_tbl is None or month_tbl.empty:
        return empty_fig("Monthly returns")
    z = month_tbl.to_numpy(float) * 100
    lim = float(np.nanmax(np.abs(z))) if np.isfinite(z).any() else 1.0
    txt = [[("" if np.isnan(v) else f"{v:.1f}") for v in row] for row in z]
    fig = go.Figure(go.Heatmap(z=z, x=list(month_tbl.columns), y=[str(i) for i in month_tbl.index], zmid=0, zmin=-lim, zmax=lim,
                               colorscale=DIVERGING, text=txt, texttemplate="%{text}", colorbar=dict(title="%"),
                               hovertemplate="%{y} %{x}: %{z:.2f}%<extra></extra>"))
    fig.update_layout(**base_layout("Monthly returns (%)", max(260, 70 + 30 * len(month_tbl)), hovermode="closest"))
    fig.update_yaxes(autorange="reversed", type="category")
    return fig


def bar_fig(x: Any, y: Any, title: str, ytitle: str, color_by_sign: bool = True, text_fmt: str = ".2f", height: int = 320) -> go.Figure:
    y = np.asarray(y, float)
    cols = [POS if v >= 0 else NEG for v in y] if color_by_sign else BLUE
    fig = go.Figure(go.Bar(x=[str(v) for v in x], y=y, marker_color=cols, text=[f"{v:{text_fmt}}" for v in y], textposition="outside",
                           cliponaxis=False))
    fig.update_layout(**base_layout(title, height, hovermode="closest", showlegend=False))
    fig.update_yaxes(title_text=ytitle)
    return fig


def hist_fig(values: Any, title: str, xtitle: str, bins: int = 40, vline: float | None = None, vline_label: str = "",
             pct_x: bool = False) -> go.Figure:
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return empty_fig(title)
    fig = go.Figure(go.Histogram(x=v * (100 if pct_x else 1), nbinsx=bins, marker_color=BLUE, opacity=0.85))
    if vline is not None and np.isfinite(vline):
        fig.add_vline(x=vline * (100 if pct_x else 1), line=dict(color=ORANGE, width=2, dash="dash"), annotation_text=vline_label,
                      annotation_position="top")
    fig.update_layout(**base_layout(title, 320, hovermode="closest", showlegend=False, bargap=0.03))
    fig.update_xaxes(title_text=xtitle)
    fig.update_yaxes(title_text="count")
    return fig


def rolling_fig(r: pd.Series, window: int = 126, ppy: int = 252) -> go.Figure:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < window + 5:
        return empty_fig("Rolling Sharpe", f"needs > {window} days")
    rs = r.rolling(window).mean() / r.rolling(window).std(ddof=1) * np.sqrt(ppy)
    rv = r.rolling(window).std(ddof=1) * np.sqrt(ppy) * 100
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    x = _naive(r.index)
    fig.add_trace(go.Scatter(x=x, y=rs.to_numpy(), name=f"Sharpe ({window}d)", line=dict(color=BLUE, width=1.6)), secondary_y=False)
    fig.add_trace(go.Scatter(x=x, y=rv.to_numpy(), name=f"Vol % ({window}d)", line=dict(color=ORANGE, width=1.2, dash="dot")), secondary_y=True)
    fig.add_hline(y=0, line=dict(color=GREY, width=1))
    fig.update_layout(**base_layout(f"Rolling Sharpe and volatility ({window} sessions)", 340))
    fig.update_yaxes(title_text="Sharpe (annualised)", secondary_y=False, gridcolor=_GRID)
    fig.update_yaxes(title_text="Volatility (% annualised)", secondary_y=True, showgrid=False)
    return fig


def line_fig(x: Any, ys: dict[str, Any], title: str, ytitle: str, xtitle: str = "", log_y: bool = False, height: int = 340) -> go.Figure:
    fig = go.Figure()
    for i, (name, y) in enumerate(ys.items()):
        fig.add_trace(go.Scatter(x=x, y=np.asarray(y, float), name=name, line=dict(color=PALETTE[i % len(PALETTE)], width=1.8)))
    fig.update_layout(**base_layout(title, height))
    fig.update_yaxes(title_text=ytitle, type="log" if log_y else "linear")
    fig.update_xaxes(title_text=xtitle)
    return fig


def mae_mfe_fig(trades: pd.DataFrame) -> go.Figure:
    from tradelab.analytics.metrics import trade_col
    mae, mfe, r = trade_col(trades, "MAE_R"), trade_col(trades, "MFE_R"), trade_col(trades, "R_net")
    if mae is None or mfe is None:
        return empty_fig("MAE / MFE (R)")
    win = (pd.Series(r, dtype=float) > 0) if r is not None else pd.Series(True, index=trades.index)
    fig = go.Figure()
    for name, mask, col in (("Winners", win, BLUE), ("Losers", ~win, VERMILLION)):
        fig.add_trace(go.Scatter(x=pd.Series(mae, dtype=float)[mask].abs(), y=pd.Series(mfe, dtype=float)[mask], mode="markers", name=name,
                                 marker=dict(color=col, size=7, opacity=0.7)))
    fig.update_layout(**base_layout("Excursions: adverse (MAE) vs favourable (MFE), in R", 360, hovermode="closest"))
    fig.update_xaxes(title_text="|MAE| (R)")
    fig.update_yaxes(title_text="MFE (R)")
    return fig


def heatmap_fig(pivot: pd.DataFrame, title: str, xtitle: str, ytitle: str, ztitle: str) -> go.Figure:
    if pivot is None or pivot.empty:
        return empty_fig(title)
    z = pivot.to_numpy(float)
    fig = go.Figure(go.Heatmap(z=z, x=[str(c) for c in pivot.columns], y=[str(i) for i in pivot.index], colorscale="Viridis",
                               colorbar=dict(title=ztitle), text=np.round(z, 2), texttemplate="%{text}",
                               hovertemplate=f"{xtitle}=%{{x}}<br>{ytitle}=%{{y}}<br>{ztitle}=%{{z:.3f}}<extra></extra>"))
    fig.update_layout(**base_layout(title, 380, hovermode="closest"))
    fig.update_xaxes(title_text=xtitle, type="category")
    fig.update_yaxes(title_text=ytitle, type="category")
    return fig


def candle_fig(bars: pd.DataFrame, trade: pd.Series, title: str, pad: int = 25, tz: str | None = None,
               overlay_cols: tuple[str, ...] = ("vwap", "poc", "vah", "val")) -> go.Figure | None:
    """Candlesticks around one trade with entry/exit markers and stop/target lines."""
    need = {"open", "high", "low", "close"}
    if bars is None or not need <= set(bars.columns) or len(bars) == 0:
        return None
    et, xt = pd.Timestamp(trade["entry_ts"]), pd.Timestamp(trade["exit_ts"])
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is not None and et.tzinfo is None:
        et, xt = et.tz_localize(idx.tz), xt.tz_localize(idx.tz)
    elif idx.tz is None and et.tzinfo is not None:
        et, xt = et.tz_convert("UTC").tz_localize(None), xt.tz_convert("UTC").tz_localize(None)
    i0 = max(int(idx.searchsorted(et, side="left")) - pad, 0)
    i1 = min(int(idx.searchsorted(xt, side="right")) + pad // 2, len(idx))
    w = bars.iloc[i0:i1]
    if w.empty:
        return None
    x = pd.DatetimeIndex(w.index)
    if x.tz is not None:
        x = x.tz_convert(tz) if tz else x
        x = x.tz_localize(None)

    def loc(ts: pd.Timestamp) -> pd.Timestamp:
        t = ts.tz_convert(tz) if (tz and ts.tzinfo is not None) else ts
        return t.tz_localize(None) if t.tzinfo is not None else t

    fig = go.Figure(go.Candlestick(x=x, open=w["open"], high=w["high"], low=w["low"], close=w["close"], name="bars",
                                   increasing_line_color=BLUE, decreasing_line_color=VERMILLION, showlegend=False))
    for c in overlay_cols:
        if c in w.columns and w[c].notna().any():
            fig.add_trace(go.Scatter(x=x, y=w[c], name=c, mode="lines", line=dict(width=1.2, dash="dot")))
    long = str(trade.get("side", "long")).lower() in ("long", "1", "1.0", "buy", "+1")
    fig.add_trace(go.Scatter(x=[loc(et)], y=[trade["entry_px"]], mode="markers", name="entry",
                             marker=dict(symbol="triangle-up" if long else "triangle-down", size=13, color=ORANGE, line=dict(width=1, color="#000"))))
    fig.add_trace(go.Scatter(x=[loc(xt)], y=[trade["exit_px"]], mode="markers", name=f"exit ({trade.get('exit_reason', '')})",
                             marker=dict(symbol="x", size=12, color=PURPLE, line=dict(width=1, color="#000"))))
    for key, col in (("initial_stop", VERMILLION), ("target", GREEN)):
        v = trade.get(key)
        if v is not None and pd.notna(v) and v != 0:
            fig.add_hline(y=float(v), line=dict(color=col, width=1.2, dash="dash"), annotation_text=key.replace("initial_", ""),
                          annotation_position="right")
    fig.update_layout(**base_layout(title, 360, hovermode="x", xaxis_rangeslider_visible=False, margin=dict(l=56, r=60, t=44, b=36)))
    fig.update_yaxes(title_text="price")
    return fig
