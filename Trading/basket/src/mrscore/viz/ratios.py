from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from mrscore.config.models import VisualizationConfig
from mrscore.core.ratio_universe import RatioJob, RatioUniverse


@dataclass(frozen=True)
class RatioPlot:
    job: RatioJob
    title: str
    series: np.ndarray
    dates: np.ndarray


def _build_title(ru: RatioUniverse, job: RatioJob) -> str:
    num_syms, den_syms = ru.job_to_symbols(job)
    num = "+".join(num_syms)
    den = "+".join(den_syms)
    return f"NUM: {num} / DEN: {den}"


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


def build_ratio_plots(
    *,
    ru: RatioUniverse,
    jobs: Iterable[RatioJob],
    config: VisualizationConfig,
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
        title = _build_title(ru, job)
        for mode in modes:
            series = _compute_series(ru=ru, job=job, mode=mode)
            dates = ru.dates if mode != "returns" else ru.dates[1:]
            plots.append(
                RatioPlot(
                    job=job,
                    title=f"{title} | {mode}",
                    series=series,
                    dates=dates,
                )
            )
    return plots


def plot_ratio_jobs(
    *,
    ru: RatioUniverse,
    jobs: Iterable[RatioJob],
    config: VisualizationConfig,
    show: bool = True,
    save_dir: Optional[str] = None,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("matplotlib is required for plotting. Install with: pip install matplotlib") from exc

    plots = build_ratio_plots(ru=ru, jobs=jobs, config=config)
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
        ax.plot(plot.dates, plot.series, linewidth=1.2)
        ax.set_title(plot.title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)

        if save_dir is not None:
            safe_title = plot.title.replace("/", "-").replace(" ", "_")
            path = f"{save_dir}/{safe_title}.png"
            fig.savefig(path, dpi=150, bbox_inches="tight")

        if show:
            plt.show()
        else:
            plt.close(fig)
