"""Robustness suite (see docs/ROBUSTNESS.md). Depends only on RunResult + an injected run_fn."""
from .bootstrap import SimResult, block_bootstrap, trade_monte_carlo
from .cost_sens import cost_sensitivity
from .grid import GridResult, expand_grid, heatmap_data, plateau_score, run_grid, score_result
from .pbo import pbo_cscv
from .psr_dsr import (count_trials, dsr, dsr_from_stats, expected_max_sr, min_trl, min_trl_from_stats, psr,
                      psr_from_stats, sr_stats, sr_variance_from_returns_matrix, trial_ledger_append, trial_ledger_read)
from .regimes import regime_breakdown, regime_summary
from .verdict import verdict
from .walkforward import WalkForwardResult, make_folds, walk_forward

__all__ = [
    "run_grid", "GridResult", "expand_grid", "heatmap_data", "plateau_score", "score_result", "walk_forward",
    "WalkForwardResult", "make_folds", "psr", "dsr", "min_trl", "psr_from_stats", "dsr_from_stats",
    "min_trl_from_stats", "expected_max_sr", "sr_stats", "sr_variance_from_returns_matrix", "pbo_cscv",
    "block_bootstrap", "trade_monte_carlo", "SimResult", "cost_sensitivity", "regime_breakdown", "regime_summary",
    "trial_ledger_append", "trial_ledger_read", "count_trials", "verdict",
]
