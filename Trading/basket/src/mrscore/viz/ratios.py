from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from mrscore.config.models import MeanEstimatorConfig, VisualizationConfig
from mrscore.core.ratio_universe import RatioJob, RatioUniverse
from mrscore.core.results import Direction
from mrscore.backtest.types import BacktestResult, Trade
from mrscore.components.mean.rolling_sma import RollingSMA
from mrscore.components.mean.ema import EMA
from mrscore.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class RatioPlot:
    job: RatioJob
    title: str
    series: np.ndarray
    dates: np.ndarray
    mode: str
    score: Optional[float] = None


def _build_title(ru: RatioUniverse, job: RatioJob, score: Optional[float]) -> str:
    num_syms, den_syms = ru.job_to_symbols(job)
    num = "+".join(num_syms)
    den = "+".join(den_syms)
    title = f"NUM: {num} / DEN: {den}"
    if score is not None:
        title = f"{title} | score={score:.6f}"
    return title


def _compute_series(
    *,
    ru: RatioUniverse,
    job: RatioJob,
    mode: str,
    eps: float = 1e-12,
) -> np.ndarray:
    ratio = ru.compute_ratio_series(job)
    if mode == "ratio":
        return ratio
    if mode == "log_ratio":
        return np.log(ratio + eps)
    if mode == "returns":
        returns = np.empty(ratio.shape[0] - 1, dtype=ratio.dtype)
        np.divide(ratio[1:], ratio[:-1], out=returns)
        returns -= 1.0
        return returns
    if mode == "zscore":
        mean = float(np.mean(ratio))
        std = float(np.std(ratio))
        if std == 0.0:
            return np.zeros_like(ratio)
        return (ratio - mean) / std
    raise ValueError(f"Unknown mode: {mode}")


def _compute_mean_series(
    series: np.ndarray,
    mean_cfg: MeanEstimatorConfig,
) -> Optional[np.ndarray]:
    if mean_cfg.type == "rolling_sma":
        estimator = RollingSMA(window=mean_cfg.params.window)
    elif mean_cfg.type == "ema":
        estimator = EMA(span=mean_cfg.params.span, min_periods=mean_cfg.params.min_periods)
    else:
        logger.warning("Mean estimator not supported for plotting: %s", mean_cfg.type)
        return None

    out = np.empty_like(series)
    for i, x in enumerate(series):
        out[i] = estimator.update(float(x))
    return out


def build_ratio_plots(
    *,
    ru: RatioUniverse,
    jobs: Iterable[RatioJob],
    config: VisualizationConfig,
    scores: Optional[dict[RatioJob, float]] = None,
    mean_config: Optional[MeanEstimatorConfig] = None,
) -> list[RatioPlot]:
    modes: list[str] = []
    if config.show_ratio:
        modes.append("ratio")
    if config.show_log_ratio:
        modes.append("log_ratio")
    if config.show_zscore:
        modes.append("zscore")
    if config.show_returns:
        modes.append("returns")

    if not modes:
        raise ValueError("VisualizationConfig has no enabled y-axis modes")

    plots: list[RatioPlot] = []
    for job in jobs:
        score = scores.get(job) if scores is not None else None
        title = _build_title(ru, job, score)
        for mode in modes:
            series = _compute_series(ru=ru, job=job, mode=mode)
            series_mean = float(np.nanmean(series))
            dates = ru.dates if mode != "returns" else ru.dates[1:]
            plots.append(
                RatioPlot(
                    job=job,
                    title=f"{title} | {mode} | mean={series_mean:.6f}",
                    series=series,
                    dates=dates,
                    mode=mode,
                    score=score,
                )
            )
    return plots


def _plot_trade_markers(
    *,
    ax,
    plot: RatioPlot,
    trades: Iterable[Trade],
) -> None:
    if plot.mode == "returns":
        return

    labels_used: set[str] = set()
    for tr in trades:
        color = "tab:green" if tr.direction == Direction.UP else "tab:red"

        entry_idx = tr.entry_index
        if 0 <= entry_idx < plot.series.size:
            label = f"entry_{tr.direction.value}"
            ax.scatter(
                plot.dates[entry_idx],
                plot.series[entry_idx],
                marker="^",
                s=40,
                color=color,
                label=label if label not in labels_used else "_nolegend_",
                zorder=5,
            )
            labels_used.add(label)

        exit_idx = tr.exit_index
        if 0 <= exit_idx < plot.series.size:
            label = f"exit_{tr.direction.value}"
            ax.scatter(
                plot.dates[exit_idx],
                plot.series[exit_idx],
                marker="x",
                s=40,
                color=color,
                label=label if label not in labels_used else "_nolegend_",
                zorder=5,
            )
            labels_used.add(label)


def plot_ratio_jobs(
    *,
    ru: RatioUniverse,
    jobs: Iterable[RatioJob],
    config: VisualizationConfig,
    scores: Optional[dict[RatioJob, float]] = None,
    mean_config: Optional[MeanEstimatorConfig] = None,
    trades_by_job: Optional[dict[RatioJob, list[Trade]]] = None,
    show: bool = True,
    save_dir: Optional[str] = None,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("matplotlib is required for plotting. Install with: pip install matplotlib") from exc

    plots = build_ratio_plots(
        ru=ru,
        jobs=jobs,
        config=config,
        scores=scores,
        mean_config=mean_config,
    )
    stop_plotting = False

    for plot in plots:
        if stop_plotting:
            break
        fig, ax = plt.subplots(figsize=(10, 4))

        def on_key(event) -> None:
            nonlocal stop_plotting
            if event.key == "escape":
                stop_plotting = True
                plt.close("all")

        fig.canvas.mpl_connect("key_press_event", on_key)
        ax.plot(plot.dates, plot.series, linewidth=1.2, label="ratio")
        mean_value = float(np.nanmean(plot.series))
        ax.axhline(mean_value, linestyle="--", linewidth=1.0, color="tab:gray", label="mean")
        if mean_config is not None and plot.series.size > 0:
            rolling = _compute_mean_series(plot.series, mean_config)
            if rolling is not None:
                ax.plot(plot.dates, rolling, linestyle="--", linewidth=1.0, color="tab:orange", label="configured_mean")
        if trades_by_job:
            trades = trades_by_job.get(plot.job)
            if trades:
                _plot_trade_markers(ax=ax, plot=plot, trades=trades)
        ax.set_title(plot.title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")

        if save_dir is not None:
            safe_title = plot.title.replace("/", "-").replace(" ", "_")
            path = f"{save_dir}/{safe_title}.png"
            fig.savefig(path, dpi=150, bbox_inches="tight")

        if show:
            plt.show()
        else:
            plt.close(fig)


def plot_equity_curve(
    *,
    result: BacktestResult,
    title: Optional[str] = None,
    show: bool = True,
    save_dir: Optional[str] = None,
) -> None:
    if not result.equity_curve:
        logger.warning("No equity curve to plot for job_id=%s", result.job_id)
        return

    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("matplotlib is required for plotting. Install with: pip install matplotlib") from exc

    xs = []
    ys = []
    for pt in result.equity_curve:
        xs.append(pt.time if pt.time is not None else pt.index)
        ys.append(pt.equity)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(xs, ys, linewidth=1.2, label="equity")
    ax.set_title(title or f"Equity Curve | {result.job_id}")
    ax.set_xlabel("Time" if result.equity_curve[0].time is not None else "Index")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    if save_dir is not None:
        safe_title = (title or f"Equity Curve | {result.job_id}").replace("/", "-").replace(" ", "_")
        path = f"{save_dir}/{safe_title}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(fig)
