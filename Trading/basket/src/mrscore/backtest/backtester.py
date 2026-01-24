from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from mrscore.config.models import RootConfig
from mrscore.core.results import Direction, EventStatus
from mrscore.io.adapters import AlignedPanel
from mrscore.io.ratio import RatioSpec, compute_basket_series, compute_ratio_series
from mrscore.backtest.types import BacktestResult, EquityPoint, Trade


def _bps_cost(notional: float, bps: float) -> float:
    return abs(notional) * (bps / 10_000.0)


def _compute_returns_series(
    *,
    series: np.ndarray,
    mode: str,
) -> np.ndarray:
    """
    Compute returns for a positive-valued level series.

    mode:
      - "simple": p[t]/p[t-1] - 1
      - "log": log(p[t]) - log(p[t-1])
    """
    series = np.asarray(series, dtype=np.float64)
    T = int(series.shape[0])
    if T < 2:
        return np.empty(0, dtype=np.float64)

    out = np.empty(T - 1, dtype=np.float64)

    if mode == "simple":
        np.divide(series[1:], series[:-1], out=out)
        out -= 1.0
        return out

    if mode == "log":
        tmp = np.empty(T - 1, dtype=np.float64)
        np.log(series[1:], out=out)
        np.log(series[:-1], out=tmp)
        out -= tmp
        return out

    raise ValueError(f"Invalid returns mode: {mode}")


@dataclass
class _OpenPosition:
    direction: Direction
    entry_index: int
    entry_time: Optional[Any]

    entry_num: float
    entry_den: float

    qty_num: float
    qty_den: float

    gross_notional_entry: float


class RatioMeanReversionBacktester:
    """
    MVP backtester for ratio mean reversion:
      - Signal: ratio or log_ratio of two baskets
      - Entry: deviation_detector on signal z-score
      - Exit: reversion_criteria (reverted) OR failure_criteria (failed) OR end (expired)
      - Execution: close-to-close fills (no latency, no next-open yet)

    Conventions:
      - Direction.DOWN => signal above mean => short ratio => short numerator, long denominator
      - Direction.UP   => signal below mean => long ratio  => long numerator, short denominator
    """

    def __init__(
        self,
        *,
        config: RootConfig,
        mean_estimator: Any,
        volatility_estimator: Any,
        deviation_detector: Any,
        reversion_criteria: Any,
        failure_criteria: Any,
    ) -> None:
        if config.backtest is None or not config.backtest.enabled:
            raise ValueError("Backtest is not enabled in config.backtest")

        self.config = config
        self.mean_estimator = mean_estimator
        self.volatility_estimator = volatility_estimator
        self.deviation_detector = deviation_detector
        self.reversion_criteria = reversion_criteria
        self.failure_criteria = failure_criteria

        # Match MeanReversionEngine volatility_unit semantics
        vu = config.volatility_estimator.params.volatility_unit
        if vu not in ("returns", "price"):
            raise ValueError("volatility_unit must be 'returns' or 'price'")
        self.volatility_unit = vu

        # Used when volatility_unit == "returns" and signal_series == "ratio"
        self.returns_mode = config.data.returns_mode  # "log" | "simple" | "none"
        if self.volatility_unit == "returns" and self.returns_mode == "none":
            raise ValueError("returns_mode must not be 'none' when volatility_unit='returns'")

        # Engine freeze semantics (treat open position as "active event")
        eng = config.engine
        self.freeze_mean_on_event = bool(eng.freeze_mean_on_event)
        self.freeze_volatility_on_event = bool(eng.freeze_volatility_on_event)

    def run_one(
        self,
        *,
        panel: AlignedPanel,
        ratio_spec: RatioSpec,
        job_id: str,
    ) -> BacktestResult:
        bt = self.config.backtest
        assert bt is not None

        dates = panel.index if hasattr(panel, "index") else None  # AlignedPanel usually has index

        # Basket leg "prices"
        num_px = compute_basket_series(panel, ratio_spec.numerator).astype(np.float64)
        den_px = compute_basket_series(panel, ratio_spec.denominator).astype(np.float64)

        # Base ratio series (positive)
        ratio = compute_ratio_series(panel, ratio_spec).astype(np.float64)
        if bt.strategy.type != "ratio_mean_reversion":
            raise ValueError(f"Unsupported strategy: {bt.strategy.type}")

        sig_mode = bt.strategy.params.signal_series
        if sig_mode == "log_ratio":
            ratio_safe = np.maximum(ratio, 1e-12)
            signal = np.log(ratio_safe)
        else:
            signal = ratio

        T = int(signal.shape[0])
        if T == 0:
            return BacktestResult(
                job_id=job_id,
                initial_cash=float(bt.initial_cash),
                final_equity=float(bt.initial_cash),
                total_return=0.0,
                trades=[] if bt.output.store_trades else None,
                equity_curve=[] if bt.output.store_equity_curve else None,
            )

        # Reset components per series (important for universe scanning)
        self.mean_estimator.reset()
        self.volatility_estimator.reset()

        # Precompute signal-returns if needed
        signal_returns: Optional[np.ndarray] = None
        if self.volatility_unit == "returns":
            if sig_mode == "log_ratio":
                # first differences are the correct "returns" for a log series
                signal_returns = np.empty(T - 1, dtype=np.float64)
                np.subtract(signal[1:], signal[:-1], out=signal_returns)
            else:
                # ratio series: use configured returns_mode
                if self.returns_mode not in ("simple", "log"):
                    raise ValueError(f"Invalid returns_mode: {self.returns_mode}")
                # ratio is already positive by construction (eps), safe for log mode
                signal_returns = _compute_returns_series(series=ratio, mode=self.returns_mode)

        cash = float(bt.initial_cash)
        pos: Optional[_OpenPosition] = None

        trades = [] if bt.output.store_trades else None
        equity_curve = [] if bt.output.store_equity_curve else None

        # Helpers for sizing
        notional_per_trade = float(bt.sizing.notional_per_trade)
        split_num, split_den = bt.hedge.leg_split

        # For warmup, reuse data.min_bars_required
        min_bars_required = int(self.config.data.min_bars_required)

        for t in range(T):
            now = dates[t] if dates is not None else None

            s = float(signal[t])
            n = float(num_px[t])
            d = float(den_px[t])

            # Update mean unless frozen by active position
            if not (self.freeze_mean_on_event and pos is not None):
                self.mean_estimator.update(s)

            # Update volatility unless frozen by active position
            if not (self.freeze_volatility_on_event and pos is not None):
                if self.volatility_unit == "price":
                    self.volatility_estimator.update(s)
                else:
                    # returns-based vol: update from t=1 onwards using returns[t-1]
                    if t >= 1:
                        assert signal_returns is not None
                        self.volatility_estimator.update(float(signal_returns[t - 1]))

            # Equity curve mark-to-market
            if equity_curve is not None:
                equity_curve.append(
                    EquityPoint(index=t, time=now, equity=cash + self._unrealized_pnl(pos, n, d))
                )

            # readiness / warmup
            if t + 1 < min_bars_required:
                continue
            if not self.mean_estimator.is_ready() or not self.volatility_estimator.is_ready():
                continue

            mean = float(self.mean_estimator.value)
            vol = float(self.volatility_estimator.value)
            if not np.isfinite(mean) or not np.isfinite(vol) or vol <= 0.0:
                continue

            z = (s - mean) / vol
            if not np.isfinite(z):
                continue

            # If we have a position, check exit conditions first
            if pos is not None:
                dur = t - pos.entry_index

                if self.reversion_criteria.is_reverted(zscore=z):
                    cash, tr = self._close_position(
                        pos=pos, t=t, now=now, n=n, d=d, status=EventStatus.REVERTED, job_id=job_id, cash=cash
                    )
                    pos = None
                    if trades is not None:
                        trades.append(tr)
                    continue

                if self.failure_criteria.is_failed(duration=dur, zscore=z):
                    cash, tr = self._close_position(
                        pos=pos, t=t, now=now, n=n, d=d, status=EventStatus.FAILED, job_id=job_id, cash=cash
                    )
                    pos = None
                    if trades is not None:
                        trades.append(tr)
                    continue

                continue

            # No open position: try to open a new one
            direction = self.deviation_detector.detect(price=s, mean=mean, volatility=vol)
            if direction is None:
                continue

            # Build two-leg position with dollar-neutral notionals
            num_notional = notional_per_trade * split_num
            den_notional = notional_per_trade * split_den

            # Direction semantics:
            # DOWN => short ratio => short numerator, long denominator
            # UP   => long ratio  => long numerator, short denominator
            if direction == Direction.DOWN:
                qty_num = -num_notional / n
                qty_den = +den_notional / d
            else:
                qty_num = +num_notional / n
                qty_den = -den_notional / d

            gross_entry = abs(qty_num * n) + abs(qty_den * d)

            # Costs on entry
            entry_costs = _bps_cost(gross_entry, bt.costs.commission_bps) + _bps_cost(
                gross_entry, bt.costs.slippage_bps
            )
            cash -= entry_costs

            pos = _OpenPosition(
                direction=direction,
                entry_index=t,
                entry_time=now,
                entry_num=n,
                entry_den=d,
                qty_num=qty_num,
                qty_den=qty_den,
                gross_notional_entry=gross_entry,
            )

        # End of series: expire open position if any
        if pos is not None:
            t = T - 1
            now = dates[t] if dates is not None else None
            n = float(num_px[t])
            d = float(den_px[t])

            cash, tr = self._close_position(
                pos=pos, t=t, now=now, n=n, d=d, status=EventStatus.EXPIRED, job_id=job_id, cash=cash
            )
            pos = None
            if trades is not None:
                trades.append(tr)

            # update last equity point if requested (ensure final reflects closure)
            if equity_curve is not None:
                equity_curve[-1] = EquityPoint(index=t, time=now, equity=cash)

        final_equity = cash
        total_return = (final_equity / float(bt.initial_cash)) - 1.0

        return BacktestResult(
            job_id=job_id,
            initial_cash=float(bt.initial_cash),
            final_equity=float(final_equity),
            total_return=float(total_return),
            trades=trades,
            equity_curve=equity_curve,
        )

    @staticmethod
    def _unrealized_pnl(pos: Optional[_OpenPosition], n: float, d: float) -> float:
        if pos is None:
            return 0.0
        return (pos.qty_num * (n - pos.entry_num)) + (pos.qty_den * (d - pos.entry_den))

    def _close_position(
        self,
        *,
        pos: _OpenPosition,
        t: int,
        now: Optional[Any],
        n: float,
        d: float,
        status: EventStatus,
        job_id: str,
        cash: float,
    ) -> tuple[float, Trade]:
        bt = self.config.backtest
        assert bt is not None

        pnl = (pos.qty_num * (n - pos.entry_num)) + (pos.qty_den * (d - pos.entry_den))
        gross_exit = abs(pos.qty_num * n) + abs(pos.qty_den * d)

        exit_costs = _bps_cost(gross_exit, bt.costs.commission_bps) + _bps_cost(
            gross_exit, bt.costs.slippage_bps
        )
        cash = cash + pnl - exit_costs

        tr = Trade(
            job_id=job_id,
            direction=pos.direction,
            status=status,
            entry_index=pos.entry_index,
            exit_index=t,
            duration=t - pos.entry_index,
            entry_time=pos.entry_time,
            exit_time=now,
            entry_num=pos.entry_num,
            entry_den=pos.entry_den,
            exit_num=n,
            exit_den=d,
            qty_num=pos.qty_num,
            qty_den=pos.qty_den,
            gross_notional_entry=pos.gross_notional_entry,
            gross_notional_exit=gross_exit,
            pnl=float(pnl),
            costs=float(exit_costs),  # entry costs already debited from cash; keep costs as exit for MVP
        )
        return cash, tr
