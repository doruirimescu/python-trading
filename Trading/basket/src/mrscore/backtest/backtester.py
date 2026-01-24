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


def _compute_returns_series(*, series: np.ndarray, mode: str) -> np.ndarray:
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
class _OpenHolding:
    """
    Single-leg holding: we hold exactly one of:
      - leg="num" : long numerator basket only
      - leg="den" : long denominator basket only
    """
    leg: str  # "num" | "den"
    entry_index: int
    entry_time: Optional[Any]
    entry_price: float
    qty: float
    gross_notional_entry: float

    # For reporting / Trade struct compatibility
    entry_num: float
    entry_den: float


class RatioMeanReversionBacktester:
    """
    Rotation (switching) strategy on a ratio:

    - Compute ratio (or log_ratio) signal and its z-score.
    - If ratio is "high" (Direction.DOWN): hold DENOMINATOR only.
    - If ratio is "low"  (Direction.UP): hold NUMERATOR only.
    - If signal flips, close current holding and open the other immediately.
    - Never hold numerator and denominator simultaneously (no pairs long/short).

    Execution: close-to-close.
    """

    def __init__(
        self,
        *,
        config: RootConfig,
        mean_estimator: Any,
        volatility_estimator: Any,
        deviation_detector: Any,
        reversion_criteria: Any,  # kept for API compatibility; not used in rotation logic
        failure_criteria: Any,    # kept for API compatibility; not used in rotation logic
    ) -> None:
        if config.backtest is None or not config.backtest.enabled:
            raise ValueError("Backtest is not enabled in config.backtest")

        self.config = config
        self.mean_estimator = mean_estimator
        self.volatility_estimator = volatility_estimator
        self.deviation_detector = deviation_detector

        # retained but not used for rotation exits
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

        # Engine freeze semantics (treat having a holding as "active event")
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

        dates = panel.dates if hasattr(panel, "dates") else (panel.index if hasattr(panel, "index") else None)

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

        # Reset components per series
        self.mean_estimator.reset()
        self.volatility_estimator.reset()

        # Precompute signal returns if needed
        signal_returns: Optional[np.ndarray] = None
        if self.volatility_unit == "returns":
            if sig_mode == "log_ratio":
                # first differences for log series
                signal_returns = np.empty(T - 1, dtype=np.float64)
                np.subtract(signal[1:], signal[:-1], out=signal_returns)
            else:
                if self.returns_mode not in ("simple", "log"):
                    raise ValueError(f"Invalid returns_mode: {self.returns_mode}")
                signal_returns = _compute_returns_series(series=ratio, mode=self.returns_mode)

        cash = float(bt.initial_cash)
        holding: Optional[_OpenHolding] = None

        trades = [] if bt.output.store_trades else None
        equity_curve = [] if bt.output.store_equity_curve else None

        min_bars_required = int(self.config.data.min_bars_required)

        # Costs (bps on traded notional)
        total_bps = float(bt.costs.commission_bps) + float(bt.costs.slippage_bps)

        # Rotation should be "all-in" into exactly one leg:
        # We will invest full current equity each time we buy.
        def current_equity(t_idx: int) -> float:
            if holding is None:
                return cash
            px = float(num_px[t_idx]) if holding.leg == "num" else float(den_px[t_idx])
            return cash + holding.qty * px

        def sell_holding(t_idx: int) -> float:
            nonlocal cash, holding
            assert holding is not None
            px = float(num_px[t_idx]) if holding.leg == "num" else float(den_px[t_idx])
            proceeds = holding.qty * px
            sell_cost = _bps_cost(proceeds, total_bps)
            cash += proceeds - sell_cost
            # Close trade record
            if trades is not None:
                exit_num = float(num_px[t_idx])
                exit_den = float(den_px[t_idx])
                entry_num = float(holding.entry_num)
                entry_den = float(holding.entry_den)

                if holding.leg == "num":
                    qty_num = holding.qty
                    qty_den = 0.0
                    pnl = holding.qty * (exit_num - holding.entry_price)
                else:
                    qty_num = 0.0
                    qty_den = holding.qty
                    pnl = holding.qty * (exit_den - holding.entry_price)

                tr = Trade(
                    job_id=job_id,
                    direction=Direction.UP if holding.leg == "num" else Direction.DOWN,
                    # We use EXPIRED to mean "rotated out" (not end-of-series).
                    status=EventStatus.EXPIRED,
                    entry_index=holding.entry_index,
                    exit_index=t_idx,
                    duration=t_idx - holding.entry_index,
                    entry_time=holding.entry_time,
                    exit_time=(dates[t_idx] if dates is not None else None),
                    entry_num=entry_num,
                    entry_den=entry_den,
                    exit_num=exit_num,
                    exit_den=exit_den,
                    qty_num=qty_num,
                    qty_den=qty_den,
                    gross_notional_entry=float(holding.gross_notional_entry),
                    gross_notional_exit=float(proceeds),
                    pnl=float(pnl),
                    costs=float(sell_cost),
                )
                trades.append(tr)

            holding = None
            return sell_cost

        def buy_leg(t_idx: int, leg: str) -> float:
            nonlocal cash, holding
            if leg not in ("num", "den"):
                raise ValueError("leg must be 'num' or 'den'")

            buy_px = float(num_px[t_idx]) if leg == "num" else float(den_px[t_idx])
            eq = cash  # we are in cash before buy_leg is called

            # Pay costs on the buy notional; invest remaining cash
            buy_cost = _bps_cost(eq, total_bps)
            invest = eq - buy_cost
            if invest <= 0.0:
                raise ValueError("Insufficient equity after costs to open position")

            qty = invest / buy_px
            cash = 0.0

            holding = _OpenHolding(
                leg=leg,
                entry_index=t_idx,
                entry_time=(dates[t_idx] if dates is not None else None),
                entry_price=buy_px,
                qty=qty,
                gross_notional_entry=invest,
                entry_num=float(num_px[t_idx]),
                entry_den=float(den_px[t_idx]),
            )
            return buy_cost

        def target_leg_from_direction(direction: Optional[Direction]) -> Optional[str]:
            # Direction.DOWN => ratio high => rotate into denominator
            # Direction.UP   => ratio low  => rotate into numerator
            if direction is None:
                return None
            return "den" if direction == Direction.DOWN else "num"

        for t in range(T):
            now = dates[t] if dates is not None else None
            s = float(signal[t])

            # Update mean unless frozen by holding
            if not (self.freeze_mean_on_event and holding is not None):
                self.mean_estimator.update(s)

            # Update volatility unless frozen by holding
            if not (self.freeze_volatility_on_event and holding is not None):
                if self.volatility_unit == "price":
                    self.volatility_estimator.update(s)
                else:
                    if t >= 1:
                        assert signal_returns is not None
                        self.volatility_estimator.update(float(signal_returns[t - 1]))

            # Equity curve mark-to-market
            if equity_curve is not None:
                equity_curve.append(EquityPoint(index=t, time=now, equity=float(current_equity(t))))

            # Warmup / readiness
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

            # Detect whether ratio is far enough from mean to justify switching
            direction = self.deviation_detector.detect(price=s, mean=mean, volatility=vol)
            tgt = target_leg_from_direction(direction)

            # Ensure we always hold *one* leg once ready:
            # - If no holding yet:
            #     - If threshold signal exists, pick the implied leg
            #     - Else default to numerator (you can change this default if you prefer)
            if holding is None:
                if tgt is None:
                    tgt = "num"
                # Buy the chosen leg with full cash
                buy_leg(t, tgt)
                continue

            # If we have a holding:
            # - If no signal (within band): keep holding
            # - If signal indicates the other leg: rotate immediately (sell then buy)
            if tgt is None:
                continue

            if tgt != holding.leg:
                # rotate: sell current, then buy target with all proceeds
                sell_holding(t)
                buy_leg(t, tgt)

        # End of series: close any open holding
        if holding is not None:
            t = T - 1
            # sell into cash and record final trade as EXPIRED (end-of-series)
            sell_holding(t)
            if equity_curve is not None:
                equity_curve[-1] = EquityPoint(index=t, time=(dates[t] if dates is not None else None), equity=cash)

        final_equity = float(cash)
        total_return = (final_equity / float(bt.initial_cash)) - 1.0

        return BacktestResult(
            job_id=job_id,
            initial_cash=float(bt.initial_cash),
            final_equity=final_equity,
            total_return=float(total_return),
            trades=trades,
            equity_curve=equity_curve,
        )
