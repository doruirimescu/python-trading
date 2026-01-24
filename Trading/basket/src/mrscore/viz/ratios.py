from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from mrscore.config.models import MeanEstimatorConfig, VisualizationConfig
from mrscore.core.ratio_universe import RatioJob, RatioUniverse
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
                    score=score,
                )
            )
    return plots


def plot_ratio_jobs(
    *,
    ru: RatioUniverse,
    jobs: Iterable[RatioJob],
    config: VisualizationConfig,
    scores: Optional[dict[RatioJob, float]] = None,
    mean_config: Optional[MeanEstimatorConfig] = None,
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
