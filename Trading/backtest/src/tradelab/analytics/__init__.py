"""Analytics over a RunResult (see docs/METRICS.md)."""
from .benchmark import benchmark_metrics
from .metrics import (compute_metrics, daily_returns, drawdown_series, drawdown_stats, jsonable, sharpe_ratio,
                      sortino_ratio, trade_col, var_cvar)
from .periodic import periodic_tables
from .rmultiple import prob_run_at_least, r_breakdowns, r_equity, r_histogram, r_multiple_stats, r_series, sqn
from .trade_stats import streaks, trade_stats

__all__ = [
    "compute_metrics", "periodic_tables", "benchmark_metrics", "trade_stats", "r_multiple_stats", "r_series",
    "r_histogram", "r_equity", "r_breakdowns", "sqn", "prob_run_at_least", "streaks", "daily_returns",
    "drawdown_series", "drawdown_stats", "sharpe_ratio", "sortino_ratio", "var_cvar", "jsonable", "trade_col",
]
