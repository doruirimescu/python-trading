from Trading.config.config import CACHING_PATH
from stateful_data_processor.file_rw import JsonFileRW
from Trading.model.timeframes import Timeframe, TIMEFRARME_ENUM
from Trading.instrument.instrument import Instrument
from Trading.model.datasource import DataSourceEnum
from Trading.model.history import History
from datetime import datetime
from Trading.utils.custom_logging import get_logger
from datetime import datetime
import math

LOGGER = get_logger("caching")

"""
    Caching is supposed to become the main gateway for data retrieval in the future.
"""


def get_caching_dir(instrument: Instrument, data_source: DataSourceEnum):
    return (
        CACHING_PATH.joinpath(data_source.value)
        .joinpath(instrument.symbol)
        .joinpath(str(instrument.timeframe))
    )


def get_caching_file_path(instrument: Instrument, data_source: DataSourceEnum):
    return get_caching_dir(instrument, data_source).joinpath("data.json")


def get_caching_file_rw(instrument: Instrument, data_source: DataSourceEnum):
    file_path = get_caching_file_path(instrument, data_source)
    return JsonFileRW(file_path)


def _get_last_n_from_client(instument: Instrument, n: int) -> History:
    from Trading.live.client.client import XTBTradingClient
    from Trading.config.config import MODE, PASSWORD, USERNAME

    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)
    history = client.get_last_n_candles_history(instument, n)
    history = History(**history)
    history.symbol = instument.symbol
    history.timeframe = instument.timeframe.period
    return history


def get_last_n_candles_from_date(
    from_date: datetime, instrument: Instrument, data_source: DataSourceEnum, n: int
) -> History:
    """
    Gets last n candles from date, including date
    """
    if from_date > datetime.now():
        raise ValueError("from_date cannot be in the future.")

    caching = get_caching_file_rw(instrument, data_source)
    LOGGER.info(
        f"Fetching last {n} candles from {from_date} for {instrument.symbol} {instrument.timeframe} file: {caching.file_name}..."
    )
    cached_data = caching.read()

    if not cached_data:
        LOGGER.info("No data in cache, fetching initial data...")
        return _fetch_and_cache_initial_data(from_date, instrument, n, caching)

    history = History(**cached_data)

    if from_date in history.date:
        return _handle_from_date_in_history(history, from_date, n, instrument, caching)

    if from_date > history.date[-1]:
        LOGGER.info("Fetching data for date greater than cached data's newest date...")
        return _fetch_and_extend_history(
            from_date, history, n, instrument, caching, after_cache=True
        )

    if from_date < history.date[0]:
        LOGGER.info("Fetching data for date earlier than cached data's oldest date...")
        return _fetch_and_extend_history(
            from_date, history, n, instrument, caching, after_cache=False
        )
    return history.slice_n_candles_before_date(from_date, n)


def _fetch_and_cache_initial_data(
    from_date: datetime, instrument: Instrument, n: int, caching
):
    now = datetime.now()
    candles_needed = n

    if (
        instrument.timeframe.period == TIMEFRARME_ENUM.ONE_MONTH.value
        and from_date < now
    ):
        days_diff = (now - from_date).days
        candles_needed += math.ceil(days_diff / 29)
    elif (
        instrument.timeframe.period == TIMEFRARME_ENUM.ONE_DAY.value and from_date < now
    ):
        candles_needed += (now - from_date).days

    new_history = _get_last_n_from_client(instrument, candles_needed)
    caching.write(new_history.__dict__)
    LOGGER.info("Initial data written to cache.")
    return new_history.slice_n_candles_before_date(from_date, n)


def _handle_from_date_in_history(
    history: History, from_date: datetime, n: int, instrument: Instrument, caching
):
    index = history.date.index(from_date)
    if index - n < 0:
        # Need more candles to satisfy the request
        LOGGER.info("Fetching more data to cover from_date...")
        additional_candles = len(history) + n - index
        new_history = _get_last_n_from_client(instrument, additional_candles)
        history.extend(new_history)
        caching.write(history.__dict__)
    return history.slice_n_candles_before_date(from_date, n)


def _fetch_and_extend_history(
    from_date: datetime,
    history: History,
    n: int,
    instrument: Instrument,
    caching,
    after_cache: bool,
):
    if after_cache:
        date_diff = (from_date - history.date[-1]).days
    else:
        date_diff = (history.date[0] - from_date).days

    candles_needed = (
        n + math.ceil(date_diff / 29)
        if instrument.timeframe.period == TIMEFRARME_ENUM.ONE_MONTH.value
        else n
    )
    new_history = _get_last_n_from_client(instrument, candles_needed)
    history.extend(new_history)
    caching.write(history.__dict__)
    LOGGER.info("Extended data written to cache.")
    return history.slice_n_candles_before_date(from_date, n)


if __name__ == "__main__":
    instrument = Instrument("EURUSD", Timeframe("1D"))
    from_date = datetime(2020, 2, 23, 1, 0)
    n = 5
    data_source = DataSourceEnum.XTB
    last_n = get_last_n_candles_from_date(from_date, instrument, data_source, n)
    print(last_n.date)
