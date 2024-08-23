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

'''
    Caching is supposed to become the main gateway for data retrieval in the future.
'''

def get_caching_dir(instrument: Instrument, data_source: DataSourceEnum):
    return CACHING_PATH.joinpath(data_source.value).joinpath(instrument.symbol).joinpath(str(instrument.timeframe))

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

def get_last_n_candles_from_date(from_date: datetime, instrument: Instrument, data_source: DataSourceEnum, n: int):
    '''
        Gets last n candles from date, including date
    '''

    caching = get_caching_file_rw(instrument, data_source)
    data = caching.read()
    if not data:
        LOGGER.info("No data in caching")
        # get_last_n_candles_history only returns the last n candles starting with today, so we need to get more data
        # calculate how many candles we need to include from today until the from_date
        now = datetime.now()
        if from_date < now:
            from_today = now - from_date
            LOGGER.info(f"From today: {from_today}")
            new_n = n
            if instrument.timeframe.period == TIMEFRARME_ENUM.ONE_MONTH.value:
                new_n = new_n + math.ceil(from_today.days/29)

        history = _get_last_n_from_client(instrument, new_n)

        caching.write(history.__dict__)
        LOGGER.info("Data written to caching")
        return history.slice_n_candles_before_date(from_date, n)
    else:
        history = History(**data)
        history_oldest_date = history.date[0]
        history_newest_date = history.date[-1]

        if from_date in history.date:
            index = history.date.index(from_date)
            if index - n < 0:
                # fetch new data
                new_n = len(history) + n - index
                LOGGER.info("Fetching new data for from_date in history")
                new_history = _get_last_n_from_client(instrument, new_n)
                history.extend(new_history)
                caching.write(history.__dict__)
        elif from_date > history_newest_date:
            diff = from_date - history_newest_date
            if instrument.timeframe.period == TIMEFRARME_ENUM.ONE_MONTH.value:
                new_n = len(history) + math.ceil(diff.days/29) + 1
            LOGGER.info("Fetching new data for from_date > history_newest_date")
            new_history = _get_last_n_from_client(instrument, new_n)
            history.extend(new_history)
            caching.write(history.__dict__)
            LOGGER.info("Data written to caching")
        elif from_date < history_oldest_date:
            diff = history_oldest_date - from_date
            if instrument.timeframe.period == TIMEFRARME_ENUM.ONE_MONTH.value:
                new_n = len(history) + math.ceil(diff.days/29) + 1
            LOGGER.info("Fetching new data for from_date < history_oldest_date")
            new_history = _get_last_n_from_client(instrument, new_n)
            history.extend(new_history)
            caching.write(history.__dict__)
            LOGGER.info("Data written to caching")
        return history.slice_n_candles_before_date(from_date, n)
