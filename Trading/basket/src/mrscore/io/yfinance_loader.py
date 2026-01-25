from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Literal, Optional, Sequence

import hashlib
import json
import re

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
    ending_date: Optional[date] = None  # if set, download period ending at this date
    cache_enabled: bool = False
    cache_path: Optional[str] = None


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

        end_date = _normalize_ending_date(req.ending_date)
        cache_dir = _prepare_cache_dir(req.cache_path) if req.cache_enabled else None
        if end_date is not None:
            logger.info("Using ending_date=%s", end_date.isoformat())
        if cache_dir is not None:
            logger.info("Cache enabled at: %s", cache_dir)

        out: Dict[str, History] = {}

        for t in req.tickers:
            logger.info("Requesting ticker history: %s", t)
            cache_path = None
            if cache_dir is not None:
                cache_path = _cache_file_path(cache_dir, t, req, end_date)
                cached = _load_cached_history(cache_path)
                if cached is not None:
                    logger.info("Cache hit: %s", cache_path)
                    out[t] = cached
                    continue

            try:
                df = _download_history(
                    yf=yf,
                    ticker=t,
                    req=req,
                    end_date=end_date,
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
            if cache_path is not None:
                _store_cached_history(cache_path, out[t])

        if not out:
            logger.error("No ticker histories could be constructed from yfinance output")
            raise ValueError("No ticker histories could be constructed from yfinance output")

        logger.info(
            "Completed yfinance load: loaded=%s requested=%s",
            sorted(out.keys()),
            list(req.tickers),
        )
        return out


def _download_history(*, yf, ticker: str, req: YFinanceLoadRequest, end_date: Optional[date]):
    if end_date is None:
        return yf.Ticker(ticker).history(
            period=req.period,
            interval=req.interval,
            auto_adjust=req.auto_adjust,
        )

    try:
        import pandas as pd
    except Exception as e:
        raise RuntimeError(
            "pandas is required for ending_date support. Install with: pip install pandas"
        ) from e

    end_ts = pd.Timestamp(end_date)
    end_ts_plus = end_ts + pd.Timedelta(days=1)
    start_ts = _compute_start_timestamp(req.period, end_date)
    df = yf.Ticker(ticker).history(
        start=start_ts,
        end=end_ts_plus,
        interval=req.interval,
        auto_adjust=req.auto_adjust,
    )
    return _truncate_to_end_date(df, end_ts)


def _truncate_to_end_date(df, end_ts):
    if df is None or df.empty:
        return df
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(None)
    mask = idx <= end_ts
    return df.loc[mask]


def _normalize_ending_date(value: Optional[date | datetime | str]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            try:
                import pandas as pd
            except Exception as e:
                raise ValueError(f"Invalid ending_date: {value}") from e
            return pd.Timestamp(value).date()
    raise ValueError(f"Unsupported ending_date type: {type(value)}")


def _compute_start_timestamp(period: str, end_date: date):
    period = period.strip().lower()
    try:
        import pandas as pd
    except Exception as e:
        raise RuntimeError(
            "pandas is required for ending_date support. Install with: pip install pandas"
        ) from e

    end_ts = pd.Timestamp(end_date)

    if period == "max":
        return None
    if period == "ytd":
        return pd.Timestamp(year=end_date.year, month=1, day=1)

    m = re.match(r"^(\d+)(mo|wk|d|y|h|m)$", period)
    if not m:
        raise ValueError(f"Unsupported period for ending_date: {period}")

    n = int(m.group(1))
    unit = m.group(2)
    if unit == "mo":
        return end_ts - pd.DateOffset(months=n)
    if unit == "y":
        return end_ts - pd.DateOffset(years=n)
    if unit == "wk":
        return end_ts - pd.DateOffset(weeks=n)
    if unit == "d":
        return end_ts - pd.DateOffset(days=n)
    if unit == "h":
        return end_ts - pd.DateOffset(hours=n)
    if unit == "m":
        return end_ts - pd.DateOffset(minutes=n)
    raise ValueError(f"Unsupported period unit: {unit}")


def _prepare_cache_dir(path: Optional[str]) -> Path:
    if not path:
        raise ValueError("cache_path must be set when cache_enabled is true")
    cache_dir = Path(path).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _cache_file_path(
    cache_dir: Path,
    ticker: str,
    req: YFinanceLoadRequest,
    end_date: Optional[date],
) -> Path:
    payload = {
        "v": 1,
        "ticker": ticker,
        "period": req.period,
        "interval": req.interval,
        "auto_adjust": req.auto_adjust,
        "ending_date": end_date.isoformat() if end_date else None,
    }
    key = json.dumps(payload, sort_keys=True)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    slug = _slugify(ticker)
    return cache_dir / f"{slug}__{digest}.npz"


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _load_cached_history(path: Path) -> Optional[History]:
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            dates = data["dates"]
            symbol = str(data["symbol"][0]) if "symbol" in data else path.stem
            open_ = _maybe_field(data, "open")
            high_ = _maybe_field(data, "high")
            low_ = _maybe_field(data, "low")
            close_ = _maybe_field(data, "close")
            return History(
                symbol=symbol,
                dates=dates,
                open=open_,
                high=high_,
                low=low_,
                close=close_,
            )
    except Exception:
        logger.warning("Failed to read cache file: %s", path, exc_info=True)
        return None


def _maybe_field(data, name: str) -> Optional[np.ndarray]:
    flag = f"has_{name}"
    if flag in data and not bool(data[flag][0]):
        return None
    if name not in data:
        return None
    arr = data[name]
    if arr.size == 0:
        return None
    return np.asarray(arr, dtype=np.float64)


def _store_cached_history(path: Path, history: History) -> None:
    try:
        np.savez_compressed(
            path,
            symbol=np.array([history.symbol]),
            dates=np.asarray(history.dates, dtype="datetime64[D]"),
            open=_field_or_empty(history.open),
            high=_field_or_empty(history.high),
            low=_field_or_empty(history.low),
            close=_field_or_empty(history.close),
            has_open=np.array([history.open is not None], dtype=bool),
            has_high=np.array([history.high is not None], dtype=bool),
            has_low=np.array([history.low is not None], dtype=bool),
            has_close=np.array([history.close is not None], dtype=bool),
        )
    except Exception:
        logger.warning("Failed to write cache file: %s", path, exc_info=True)


def _field_or_empty(arr: Optional[np.ndarray]) -> np.ndarray:
    if arr is None:
        return np.asarray([], dtype=np.float64)
    return np.asarray(arr, dtype=np.float64)


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
