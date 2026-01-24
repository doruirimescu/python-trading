from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Literal, Optional, Sequence

import numpy as np

from mrscore.io.history import History


@dataclass(frozen=True)
class YFinanceLoadRequest:
    tickers: Sequence[str]
    period: str = "5y"                  # yfinance period string
    interval: str = "1d"                # 1d, 1h, etc
    auto_adjust: bool = True
    group_by: Literal["ticker", "column"] = "ticker"
    threads: bool = True
    progress: bool = False


class YFinanceLoader:
    """
    I/O boundary: download OHLCV from yfinance and convert into mrscore.io.history.History.

    Output:
      Dict[ticker, History] where History fields are float64 arrays and dates are np.datetime64[D].
    """

    def load(self, req: YFinanceLoadRequest) -> Dict[str, History]:
        try:
            import yfinance as yf
        except Exception as e:
            raise RuntimeError(
                "yfinance is required for YFinanceLoader. Install with: pip install yfinance"
            ) from e

        if not req.tickers:
            raise ValueError("tickers must be non-empty")

        # One batched call
        df = yf.download(
            tickers=list(req.tickers),
            period=req.period,
            interval=req.interval,
            auto_adjust=req.auto_adjust,
            group_by=req.group_by,
            threads=req.threads,
            progress=req.progress,
        )

        if df is None or df.empty:
            raise ValueError("yfinance returned no data")

        # Convert index -> np.datetime64[D] (daily) or ns if you later need intraday
        # For now, cast to day resolution consistently.
        dates = df.index.to_numpy(dtype="datetime64[D]")

        out: Dict[str, History] = {}

        # yfinance output shapes:
        # - single ticker: columns = ["Open","High","Low","Close","Adj Close","Volume"] (not MultiIndex)
        # - multiple tickers: MultiIndex columns: (field, ticker) OR (ticker, field) depending on group_by
        cols = df.columns

        if getattr(cols, "nlevels", 1) == 1:
            # Single ticker case: df is one table
            t = req.tickers[0]
            out[t] = _history_from_single_df(t, dates, df)
            return out

        # MultiIndex case
        if req.group_by == "ticker":
            # columns: (ticker, field)
            # Example: df[ticker]["Open"]
            for t in req.tickers:
                if t not in df.columns.get_level_values(0):
                    continue
                sub = df[t]
                if sub is None or sub.empty:
                    continue
                out[t] = _history_from_single_df(t, dates, sub)
        else:
            # group_by="column": columns: (field, ticker)
            # Example: df["Open"][ticker]
            fields = df.columns.get_level_values(0)
            for t in req.tickers:
                if t not in df.columns.get_level_values(1):
                    continue
                sub = df.xs(t, axis=1, level=1, drop_level=True)
                if sub is None or sub.empty:
                    continue
                out[t] = _history_from_single_df(t, dates, sub)

        if len(out) < len(req.tickers):
            # Retry missing tickers individually to reduce flaky batch failures.
            missing = [t for t in req.tickers if t not in out]
            for t in missing:
                single = yf.download(
                    tickers=[t],
                    period=req.period,
                    interval=req.interval,
                    auto_adjust=req.auto_adjust,
                    group_by="ticker",
                    threads=False,
                    progress=req.progress,
                )
                if single is None or single.empty:
                    continue
                single_dates = single.index.to_numpy(dtype="datetime64[D]")
                out[t] = _history_from_single_df(t, single_dates, single)

        if not out:
            raise ValueError("No ticker histories could be constructed from yfinance output")

        return out


def _history_from_single_df(ticker: str, dates: np.ndarray, df) -> History:
    """
    df columns are expected to include Open/High/Low/Close (case-insensitive).
    """
    # Normalize column names
    colmap = {c.lower().replace(" ", ""): c for c in df.columns}

    def get(name: str) -> Optional[np.ndarray]:
        key = name.lower()
        # yfinance uses "Adj Close" sometimes; we ignore it because you typically want adjusted via auto_adjust=True
        if key not in colmap:
            return None
        arr = df[colmap[key]].to_numpy(dtype=np.float64, copy=False)
        return np.asarray(arr, dtype=np.float64)

    open_ = get("open")
    high_ = get("high")
    low_ = get("low")
    close_ = get("close")

    if close_ is None and open_ is None and high_ is None and low_ is None:
        raise ValueError(f"{ticker}: missing OHLC columns")

    # Ensure lengths match dates (yfinance should, but enforce)
    n = len(dates)
    for a in (open_, high_, low_, close_):
        if a is not None and len(a) != n:
            raise ValueError(f"{ticker}: column length mismatch vs dates")

    return History(
        symbol=ticker,
        dates=np.asarray(dates),
        open=open_,
        high=high_,
        low=low_,
        close=close_,
    )
