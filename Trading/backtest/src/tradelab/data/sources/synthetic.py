"""Seeded synthetic data: daily GBM and intraday 1m with realistic sessions/volume.

All randomness derives from (seed, symbol) so results are reproducible.  Prices sit on the
instrument tick grid.  Optional ``bid_vol``/``ask_vol`` (aggressor volume) correlated with returns.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ...util.seeds import rng_for
from ..base import clip_range
from ..calendar import ET, freq_to_timedelta, is_daily, trading_days
from ..instruments import get_instrument


class SyntheticSource:
    name = "synthetic"

    def load(
        self,
        symbol: str,
        start: str | None,
        end: str | None,
        freq: str,
        *,
        adjusted: bool = True,
        seed: int = 0,
        mu: float = 0.08,
        sigma: float = 0.20,
        p0: float | None = None,
        session: str = "rth",           # rth | globex (intraday only)
        bid_ask: bool = False,
        base_volume: float | None = None,
        gap_sigma: float = 0.4,
        **_,
    ) -> pd.DataFrame:
        spec = get_instrument(symbol)
        if is_daily(freq):
            return self._daily(symbol, spec, start or "2005-01-03", end or "2024-12-31", seed, mu, sigma, p0, base_volume)
        base = self._intraday_1m(symbol, spec, start or "2020-01-02", end or "2020-03-31", seed, mu, sigma, p0, session, bid_ask, base_volume, gap_sigma)
        if freq_to_timedelta(freq) == pd.Timedelta(minutes=1):
            return base
        from ..resample import resample_bars
        res = resample_bars(base, spec, "1m", freq)
        return res.drop(columns=[c for c in ("session_date", "session_type", "bar_in_session", "is_session_last", "partial") if c in res.columns])

    # ------------------------------------------------------------------ daily
    def _daily(self, symbol, spec, start, end, seed, mu, sigma, p0, base_volume):
        rng = rng_for(seed, "daily", symbol)
        days = trading_days(start, end)
        n = len(days)
        p0 = p0 or (4000.0 if spec.kind == "future" else 100.0)
        # slow volatility regimes
        reg = np.repeat(rng.choice([0.6, 1.0, 1.8], size=n // 60 + 2, p=[0.3, 0.5, 0.2]), 60)[:n]
        z = rng.standard_normal(n)
        sig_d = sigma * reg / np.sqrt(252)
        lr = (mu - 0.5 * (sigma * reg) ** 2) / 252 + sig_d * z
        gap = sig_d * 0.3 * rng.standard_normal(n)
        close = p0 * np.exp(np.cumsum(lr))
        prev = np.r_[p0, close[:-1]]
        open_ = prev * np.exp(gap)
        rng_hi = np.abs(rng.standard_normal(n)) * sig_d * 0.5
        rng_lo = np.abs(rng.standard_normal(n)) * sig_d * 0.5
        high = np.maximum(open_, close) * np.exp(rng_hi)
        low = np.minimum(open_, close) * np.exp(-rng_lo)
        bv = base_volume or (1e6 if spec.kind == "equity" else 5e5)
        vol = bv * np.exp(0.4 * rng.standard_normal(n)) * (1 + 0.5 * np.abs(z))
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": np.round(vol)}, index=days)
        df = self._round(df, spec.tick_size)
        loc = (df.index + pd.Timedelta(hours=16)).tz_localize(ET)
        df.index = loc.tz_convert("UTC")
        df.index.name = "ts"
        return clip_range(df, start, end)

    @staticmethod
    def _round(df, tick):
        if tick and tick > 0:
            for c in ("open", "high", "low", "close"):
                df[c] = np.round(df[c] / tick) * tick
            df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
            df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
        return df

    # --------------------------------------------------------------- intraday
    def _intraday_1m(self, symbol, spec, start, end, seed, mu, sigma, p0, session, bid_ask, base_volume, gap_sigma):
        rng = rng_for(seed, "1m", symbol)
        days = trading_days(start, end)
        nd = len(days)
        if session == "globex":
            offs = np.arange(-360 + 1, 17 * 60 + 1)       # bar-end minutes rel. to session_date 00:00 local
        else:
            offs = np.arange(9 * 60 + 30 + 1, 16 * 60 + 1)
        nb = len(offs)
        local = days.values[:, None] + (offs.astype("timedelta64[m]"))[None, :].astype("timedelta64[ns]")
        flat = pd.DatetimeIndex(local.ravel())
        idx = flat.tz_localize(ET).tz_convert("UTC")
        m_of_day = np.tile(offs % 1440, nd).astype(float)
        is_rth = (m_of_day > 570) & (m_of_day <= 960)
        # volume and vol-of-vol intraday shape (U-shape in RTH, thin ETH)
        shape = np.where(
            is_rth,
            1.0 + 2.5 * np.exp(-(m_of_day - 570) / 20.0) + 1.5 * np.exp(-(960 - m_of_day) / 30.0),
            0.12,
        )
        N = nd * nb
        p0 = p0 or (15000.0 if spec.kind == "future" else 100.0)
        sig_m = sigma / np.sqrt(252 * 390)
        reg = np.repeat(rng.choice([0.6, 1.0, 1.7], size=nd // 15 + 2, p=[0.3, 0.5, 0.2]), 15)[:nd]
        reg_b = np.repeat(reg, nb)
        z = rng.standard_normal(N)
        inc = mu / (252 * 390) + sig_m * reg_b * np.sqrt(shape) * np.where(is_rth, 1.0, 0.6) * z
        first = np.zeros(N, bool)
        first[::nb] = True
        gap = np.zeros(N)
        if session != "globex":
            gap[first] = sig_m * np.sqrt(390) * gap_sigma * reg * rng.standard_normal(nd)
        L = np.cumsum(inc + gap)
        close = p0 * np.exp(L)
        open_ = np.r_[p0, close[:-1]] * np.exp(gap)
        if session != "globex":
            open_ = np.where(first, np.r_[p0, close[:-1]] * np.exp(gap), np.r_[p0, close[:-1]])
        else:
            open_ = np.r_[p0, close[:-1]]
        wick_h = np.abs(rng.standard_normal(N)) * sig_m * reg_b * np.sqrt(shape) * 0.6
        wick_l = np.abs(rng.standard_normal(N)) * sig_m * reg_b * np.sqrt(shape) * 0.6
        high = np.maximum(open_, close) * np.exp(wick_h)
        low = np.minimum(open_, close) * np.exp(-wick_l)
        bv = base_volume or (2500.0 if spec.kind == "future" else 2000.0)
        vol = np.round(bv * shape * np.exp(0.5 * rng.standard_normal(N)) * (1 + 0.3 * np.abs(z))) + 1
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)
        df = self._round(df, spec.tick_size)
        if bid_ask:
            ret = (df["close"].to_numpy() - df["open"].to_numpy()) / (df["close"].to_numpy() * sig_m * np.sqrt(shape) + 1e-12)
            share = np.clip(0.5 + 0.22 * np.tanh(ret) + 0.06 * rng.standard_normal(N), 0.03, 0.97)
            ask = np.round(vol * share)
            df["ask_vol"] = ask
            df["bid_vol"] = vol - ask
        df.index.name = "ts"
        return clip_range(df, start, end)
