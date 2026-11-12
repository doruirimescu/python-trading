"""The strategy the research arrived at, and what it says to do now.

**On payment day**, look at yesterday's close:

1. S&P 500 above its 200-day average, and the 10-year Treasury yield not up more than 0.6 points over the last
   six months (126 trading days): be **six payments ahead** (borrow on margin and invest now), as far as the
   account allows (debt at most 25% of the position).
2. Otherwise: do not borrow. Payments repay the debt first, then buy as usual.

It never holds a payment back in cash: in no era and under no signal tested did waiting pay.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from perfectshape.dca.account import AccountConfig
from perfectshape.dca.policy import Policy, trend_policy


@dataclass(frozen=True)
class Strategy:
    ma: int = 200                 # days of the average
    months: float = 6.0           # payments borrowed while the conditions hold
    guard_rise: float = 0.6       # no borrowing while the 10-year yield rose more than this (points) ...
    guard_days: int = 126         # ... over this many trading days; 0 = no guard
    monthly: bool = True          # decide on payment day only
    max_debt_share: float = 0.25  # debt at most this share of the position

    def guard(self, g):
        return (g["y10"] - g["y10"].shift(self.guard_days)) > self.guard_rise

    def policy(self) -> Policy:
        return trend_policy(self.ma, on=-self.months, monthly=self.monthly,
                            veto=self.guard if self.guard_days else None)

    def account(self, **kw) -> AccountConfig:
        return AccountConfig(initial_margin=1.0 - self.max_debt_share, **kw)


RECOMMENDED = Strategy()


def decision(market, features, s: Strategy = RECOMMENDED) -> dict:
    """What the strategy says for a payment made at the next close, from the latest bar of ``market``."""
    px = features["px"]
    avg = px.rolling(s.ma).mean()
    rise = market["y10"] - market["y10"].shift(s.guard_days) if s.guard_days else market["y10"] * 0
    above = bool(px.iloc[-1] > avg.iloc[-1])
    guarded = bool(s.guard_days and rise.iloc[-1] > s.guard_rise)
    borrow = above and not guarded
    since = int(np.argmax((px > avg).to_numpy()[::-1] != above)) if len(px) else 0
    if borrow:
        text = (f"Borrow: be {s.months:g} payments ahead (debt up to {s.months:g} payments, never above "
                f"{s.max_debt_share:.0%} of the account).")
    elif above:
        text = "No new borrowing: the 10-year yield has risen too fast. Payments repay any debt first, then buy."
    else:
        text = "No new borrowing: the S&P 500 is below its average. Payments repay any debt first, then buy."
    return {"date": str(market.index[-1].date()), "px": float(px.iloc[-1]), "avg": float(avg.iloc[-1]),
            "vs_avg": float(px.iloc[-1] / avg.iloc[-1] - 1.0), "above": above, "days_in_state": since,
            "y10": float(market["y10"].iloc[-1]), "y10_rise": float(rise.iloc[-1]), "guarded": guarded,
            "y3m": float(market["y3m"].iloc[-1]), "target": -s.months if borrow else 0.0, "borrow": borrow, "text": text,
            "vix": float(market["vix"].iloc[-1]) if "vix" in market and np.isfinite(market["vix"].iloc[-1]) else None}




# ---------------------------------------------------------------- borrowing sized against the account

@dataclass(frozen=True)
class ExposureStrategy:
    """The second strategy: the account's exposure (position / equity) follows the trend, and it sells.

    Above the 200-day average (and no rate shock): ``up`` (1.5 = borrowed half the account's equity). Below it:
    ``down`` (0.5 = half the account in cash, earning the bill rate). Checked every day on the previous close;
    traded when the account is more than 2% of equity off."""

    up: float = 1.5
    down: float = 0.5
    ma: int = 200
    guard_rise: float = 0.6
    guard_days: int = 126
    band: float = 0.0

    def rule(self):
        from perfectshape.dca.rules import Rule, rate_guard, trend, unless

        e = trend(self.up, self.down, self.ma, self.band)
        if self.guard_days:
            e = unless(e, rate_guard(self.guard_rise, self.guard_days))
        return Rule(f"Trend {self.up:g} / {self.down:g} + rate guard", e, True, "strategy")


EXPOSURE_RECOMMENDED = ExposureStrategy()


def exposure_decision(market, features, s: ExposureStrategy = EXPOSURE_RECOMMENDED) -> dict:
    """The exposure the strategy wants at the next close, from the latest bar."""
    px = features["px"]
    avg = px.rolling(s.ma).mean()
    above = bool(px.iloc[-1] > avg.iloc[-1])
    rise = float(market["y10"].iloc[-1] - market["y10"].iloc[-1 - s.guard_days]) if s.guard_days else 0.0
    guarded = bool(s.guard_days and rise > s.guard_rise)
    e = s.up if above else s.down
    if guarded:
        e = min(e, 1.0)
    if e > 1:
        text = f"Exposure {e:g}: borrow {e - 1:.0%} of the account's equity and hold it in the S&P 500."
    elif e < 1:
        text = f"Exposure {e:g}: keep {1 - e:.0%} of the account in cash (T-bills); no debt."
    else:
        text = "Exposure 1: fully invested, no debt (the 10-year yield has risen too fast to borrow)."
    return {"exposure": e, "above": above, "guarded": guarded, "y10_rise": rise, "text": text}
