from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional, Sequence

import numpy as np

from mrscore.io.history import History
from mrscore.utils.logging import get_logger


logger = get_logger(__name__)


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

        logger.info(
            "Starting yfinance load: tickers=%s period=%s interval=%s auto_adjust=%s",
            list(req.tickers),
            req.period,
            req.interval,
            req.auto_adjust,
        )

        out: Dict[str, History] = {}

        for t in req.tickers:
            logger.info("Requesting ticker history: %s", t)
            try:
                df = yf.Ticker(t).history(
                    period=req.period,
                    interval=req.interval,
                    auto_adjust=req.auto_adjust,
                )
            except Exception as exc:
                logger.exception("Failed to download ticker history: %s", t)
                raise RuntimeError(f"Failed to load ticker history for {t}") from exc

            if df is None or df.empty:
                logger.error("Ticker returned empty dataframe: %s", t)
                raise RuntimeError(f"Ticker {t} returned empty dataframe")

            dates = df.index.to_numpy(dtype="datetime64[D]")
            logger.info("Parsing ticker dataframe: %s rows=%d", t, len(dates))
            out[t] = _history_from_single_df(t, dates, df)

        if not out:
            logger.error("No ticker histories could be constructed from yfinance output")
            raise ValueError("No ticker histories could be constructed from yfinance output")

        logger.info(
            "Completed yfinance load: loaded=%s requested=%s",
            sorted(out.keys()),
            list(req.tickers),
        )
        return out


def _history_from_single_df(ticker: str, dates: np.ndarray, df) -> History:
    """
    df columns are expected to include Open/High/Low/Close (case-insensitive).
    """
    logger.info("Parsing OHLC columns: %s columns=%s", ticker, list(df.columns))
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
