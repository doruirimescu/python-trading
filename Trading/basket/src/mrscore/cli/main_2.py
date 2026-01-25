# main_2.py
from __future__ import annotations

import csv
import numpy as np

from mrscore.config.loader import load_config
from mrscore.core.ratio_universe import RatioUniverse, RatioJob
from mrscore.core.ranking import TopKRanker
from mrscore.io.adapters import AlignedPanel, build_price_panel
from mrscore.io.history import OHLC
from mrscore.io.ratio import RatioSpec, build_equal_weight_basket
from mrscore.io.yfinance_loader import YFinanceLoader, YFinanceLoadRequest
from mrscore.utils.logging import get_logger
from mrscore.viz import plot_ratio_jobs

# Pick ONE of these imports depending on where you placed it:
# from mrscore.app.composition_root import build_app
from mrscore.app.composition_root import build_app


logger = get_logger(__name__)


def _bps_cost(notional: float, bps: float) -> float:
    return abs(notional) * (bps / 10_000.0)


def _compute_returns_inplace(
    *,
    prices: np.ndarray,
    returns_out: np.ndarray,
    tmp_out: np.ndarray | None,
    mode: str,
) -> np.ndarray:
    """
    Compute returns from prices into a preallocated output array.

    prices: shape (T,)
    returns_out: shape (T-1,)
    tmp_out: shape (T-1,) if mode=="log", else None
    mode: "log" | "simple"
    """
    if mode == "simple":
        np.divide(prices[1:], prices[:-1], out=returns_out)
        returns_out -= 1.0
        return returns_out

    if mode == "log":
        if tmp_out is None:
            raise ValueError("tmp_out is required for log returns")
        np.log(prices[1:], out=returns_out)   # log(p_t)
        np.log(prices[:-1], out=tmp_out)      # log(p_{t-1})
        returns_out -= tmp_out
        return returns_out

    raise ValueError(f"Invalid returns mode: {mode}")


def _select_top_k_jobs(
    *,
    ru: RatioUniverse,
    engine,  # MeanReversionEngine, typed loosely to avoid import cycles
    returns_mode: str,
    vol_unit: str,
    k_num: int,
    k_den: int,
    max_jobs: int | None,
    top_k: int,
) -> tuple[list[RatioJob], dict[RatioJob, float], int]:
    """
    Streaming top-k selection by REAL engine score.

    - avoids storing all scores
    - O(J log K)
    - uses preallocated buffers for ratio + returns
    """
    ranker = TopKRanker(top_k)

    # Reuse a buffer to avoid allocating (T,) arrays for every ratio
    T = ru._X.shape[0]  # if you prefer, add a public property on RatioUniverse
    price_buf = np.empty(T, dtype=np.float64)

    # Returns buffers (only if needed)
    ret_buf = None
    tmp_buf = None
    if vol_unit == "returns":
        if returns_mode == "none":
            raise ValueError("volatility_unit is 'returns' but returns_mode is 'none'")
        ret_buf = np.empty(T - 1, dtype=np.float64)
        if returns_mode == "log":
            tmp_buf = np.empty(T - 1, dtype=np.float64)

    # Track scores for plotting
    scores: dict[RatioJob, float] = {}

    processed = 0
    for job in ru.iter_ratio_jobs(k_num=k_num, k_den=k_den, max_jobs=max_jobs):
        ru.compute_ratio_series_into(price_buf, job)

        # Prepare returns if required by engine/vol unit
        returns = None
        if vol_unit == "returns":
            assert ret_buf is not None
            returns = _compute_returns_inplace(
                prices=price_buf,
                returns_out=ret_buf,
                tmp_out=tmp_buf,
                mode=returns_mode,
            )

        result = engine.run(prices=price_buf, returns=returns, dates=ru.dates)
        score = float(result.score)

        # Skip NaN scores (e.g., record_empty_scores=False with 0 events)
        if not np.isfinite(score):
            continue

        ranker.consider(job=job, score=score)
        # store score for this job if it makes it into the heap; to keep it simple, store always
        scores[job] = score
        processed += 1

    top = ranker.items_sorted(descending=True)

    if top:
        logger.info("Top-1 score=%f job=%s", top[0].score, top[0].job)
        logger.info("Top-%d cutoff score=%f", len(top), top[-1].score)

    jobs = [r.job for r in top]
    # Only return scores for the selected top jobs (keeps plot legend clean)
    top_scores = {r.job: r.score for r in top}
    return jobs, top_scores, processed


def _job_to_ratio_spec(ru: RatioUniverse, job: RatioJob) -> tuple[RatioSpec, str]:
    lib_num = ru.get_basket_library(job.k_num)
    lib_den = lib_num if job.k_num == job.k_den else ru.get_basket_library(job.k_den)

    num_idx = lib_num.baskets[job.num_id]
    den_idx = lib_den.baskets[job.den_id]

    num_syms, den_syms = ru.job_to_symbols(job)
    job_id = f"{'+'.join(num_syms)} / {'+'.join(den_syms)}"

    spec = RatioSpec(
        numerator=build_equal_weight_basket(num_idx),
        denominator=build_equal_weight_basket(den_idx),
        eps=1e-12,
    )
    return spec, job_id


def _format_date(value) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _summarize_trades_for_job(
    *,
    job: RatioJob,
    job_id: str,
    raw_panel,
    ratio_spec: RatioSpec,
    result,
    total_bps: float,
) -> tuple[str, list[dict[str, object]]]:
    lines: list[str] = []
    rows: list[dict[str, object]] = []
    trades = result.trades or []
    if not trades:
        return f"Summary {job_id}: no trades", rows

    lines.append(f"Summary for {job_id}")
    lines.append(
        f"  Trades: {len(trades)} | Total return: {result.total_return:.4f} | Initial cash: {result.initial_cash:.2f}"
    )
    running_equity = float(result.initial_cash)

    num_idx = ratio_spec.numerator.indices
    den_idx = ratio_spec.denominator.indices
    num_syms = [raw_panel.symbols[i] for i in num_idx]
    den_syms = [raw_panel.symbols[i] for i in den_idx]

    for i, tr in enumerate(trades, start=1):
        entry_date = _format_date(tr.entry_time)
        exit_date = _format_date(tr.exit_time)
        entry_costs = _bps_cost(tr.gross_notional_entry, total_bps)
        exit_costs = float(tr.costs)
        net_profit = float(tr.pnl) - entry_costs - exit_costs
        running_equity += net_profit

        lines.append(f"  Trade {i}: {entry_date} -> {exit_date}")
        lines.append(
            f"    direction={tr.direction.value} status={tr.status.value} duration={tr.duration} "
            f"gross_entry={tr.gross_notional_entry:.2f} gross_exit={tr.gross_notional_exit:.2f}"
        )
        lines.append(
            f"    pnl={tr.pnl:.2f} costs={entry_costs + exit_costs:.2f} net={net_profit:.2f} "
            f"equity={running_equity:.2f}"
        )

        # Use original (unnormalized) prices for reporting.
        entry_num_px = raw_panel.values[tr.entry_index, num_idx]
        exit_num_px = raw_panel.values[tr.exit_index, num_idx]
        entry_den_px = raw_panel.values[tr.entry_index, den_idx]
        exit_den_px = raw_panel.values[tr.exit_index, den_idx]

        if tr.qty_num is not None and len(tr.qty_num) > 0:
            for sym, qty, px_in, px_out in zip(num_syms, tr.qty_num, entry_num_px, exit_num_px):
                if qty == 0.0:
                    continue
                side = "BUY" if qty > 0 else "SELL"
                lines.append(f"      {side} {sym} qty={qty:.6f} entry={px_in:.4f} exit={px_out:.4f}")
                rows.append(
                    {
                        "job_id": job_id,
                        "trade_index": i,
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "direction": tr.direction.value,
                        "duration": tr.duration,
                        "symbol": sym,
                        "side": side,
                        "qty": float(qty),
                        "entry_price": float(px_in),
                        "exit_price": float(px_out),
                        "gross_entry": float(tr.gross_notional_entry),
                        "gross_exit": float(tr.gross_notional_exit),
                        "pnl": float(tr.pnl),
                        "costs": float(entry_costs + exit_costs),
                        "net_profit": float(net_profit),
                        "running_equity": float(running_equity),
                    }
                )

        if tr.qty_den is not None and len(tr.qty_den) > 0:
            for sym, qty, px_in, px_out in zip(den_syms, tr.qty_den, entry_den_px, exit_den_px):
                if qty == 0.0:
                    continue
                side = "BUY" if qty > 0 else "SELL"
                lines.append(f"      {side} {sym} qty={qty:.6f} entry={px_in:.4f} exit={px_out:.4f}")
                rows.append(
                    {
                        "job_id": job_id,
                        "trade_index": i,
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "direction": tr.direction.value,
                        "duration": tr.duration,
                        "symbol": sym,
                        "side": side,
                        "qty": float(qty),
                        "entry_price": float(px_in),
                        "exit_price": float(px_out),
                        "gross_entry": float(tr.gross_notional_entry),
                        "gross_exit": float(tr.gross_notional_exit),
                        "pnl": float(tr.pnl),
                        "costs": float(entry_costs + exit_costs),
                        "net_profit": float(net_profit),
                        "running_equity": float(running_equity),
                    }
                )

    return "\n".join(lines), rows


def main():
    cfg = load_config("config.yaml")  # loader returns RootConfig in your project
    tickers = cfg.data.tickers
    period = cfg.data.period
    interval = cfg.data.interval

    # Build composed application (engine + components)
    app = build_app(cfg)
    engine = app.engine

    # Determine returns_mode and volatility_unit for correct engine invocation
    returns_mode = cfg.data.returns_mode  # "log" | "simple" | "none"
    vol_unit = cfg.volatility_estimator.params.volatility_unit  # "returns" | "price"

    logger.info("Starting main_2: tickers=%s", tickers)
    loader = YFinanceLoader()
    histories = loader.load(
        YFinanceLoadRequest(tickers=tickers, period=period, interval=interval, auto_adjust=True)
    )
    logger.info("Loaded histories: %d tickers", len(histories))

    panel_raw = build_price_panel(
        histories=histories,
        symbols=tickers,
        field=OHLC.CLOSE,
        align="intersection",
        normalize_by_first=False,
    )
    panel_for_ru = AlignedPanel(
        dates=panel_raw.dates,
        symbols=panel_raw.symbols,
        values=panel_raw.values.copy(),
    )
    ru = RatioUniverse(panel=panel_for_ru, normalize_by_first=True, eps=1e-12)

    top_k = cfg.visualization.top_k or 10
    ratio_cfg = cfg.ratio_universe

    logger.info(
        "Ranking top %d ratio jobs by engine score (k_num=%d k_den=%d max_jobs=%s returns_mode=%s vol_unit=%s)",
        top_k,
        ratio_cfg.k_num,
        ratio_cfg.k_den,
        ratio_cfg.max_jobs,
        returns_mode,
        vol_unit,
    )

    jobs, scores, processed_jobs = _select_top_k_jobs(
        ru=ru,
        engine=engine,
        returns_mode=returns_mode,
        vol_unit=vol_unit,
        k_num=ratio_cfg.k_num,
        k_den=ratio_cfg.k_den,
        max_jobs=ratio_cfg.max_jobs,
        top_k=top_k,
    )
    total_possible = ru.estimate_ratio_count(
        k_num=ratio_cfg.k_num,
        k_den=ratio_cfg.k_den,
        unordered_if_equal_k=ratio_cfg.unordered_if_equal_k,
        disallow_overlap=ratio_cfg.disallow_overlap,
    )
    logger.info(
        "Ratio jobs considered: %d of ~%d possible (C(N,k) based upper bound; overlap filter may reduce actual)",
        processed_jobs,
        total_possible,
    )

    trades_by_job = None
    equity_by_job = None
    if app.backtester is not None:
        bt_results = []
        trades_by_job = {}
        equity_by_job = {}
        trade_rows: list[dict[str, object]] = []
        total_bps = float(cfg.backtest.costs.commission_bps + cfg.backtest.costs.slippage_bps) if cfg.backtest else 0.0
        for job in jobs:
            spec, job_id = _job_to_ratio_spec(ru, job)
            result = app.backtester.run_one(panel=panel_raw, ratio_spec=spec, job_id=job_id)
            bt_results.append(result)
            trades_by_job[job] = result.trades or []
            equity_by_job[job] = result
            logger.info(
                "Backtest %s: return=%.2f%% trades=%d",
                job_id,
                result.total_return * 100.0,
                len(result.trades or []),
            )
            summary, rows = _summarize_trades_for_job(
                job=job,
                job_id=job_id,
                raw_panel=panel_raw,
                ratio_spec=spec,
                result=result,
                total_bps=total_bps,
            )
            logger.info("%s", summary)
            trade_rows.extend(rows)

        if trade_rows:
            csv_path = "trade_summary.csv"
            fieldnames = list(trade_rows[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(trade_rows)
            logger.info("Wrote trade summary CSV: %s rows=%d", csv_path, len(trade_rows))

    plot_ratio_jobs(
        ru=ru,
        jobs=jobs,
        config=cfg.visualization,
        scores=scores,
        mean_config=cfg.mean_estimator,
        trades_by_job=trades_by_job,
        equity_by_job=equity_by_job,
        show=True,
    )


if __name__ == "__main__":
    main()
