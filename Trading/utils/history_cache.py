import os
from datetime import date, datetime
from typing import Dict, Optional

from stateful_data_processor.file_rw import JsonFileRW

from Trading.config.config import HISTORY_CACHE_PATH
from Trading.instrument import Instrument
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger(__file__)

def make_cache_dir():
    if not os.path.exists(HISTORY_CACHE_PATH):
        os.makedirs(HISTORY_CACHE_PATH)

def get_history_days(instrument: Instrument, n_days: int, date_today: Optional[datetime.date] = None) -> Optional[Dict]:
    # if instrument is
    if instrument.timeframe.get_name() != '1-day':
        raise ValueError('Timeframe must be 1-day')
    make_cache_dir()
    symbol = instrument.symbol
    timeframe = instrument.timeframe.get_name()
    if not date_today:
        today = date.today().isoformat()
    else:
        today = date_today.isoformat()

    filename = f'{symbol}_{timeframe}_{str(n_days)}_{today}.json'

    cache_file = HISTORY_CACHE_PATH.joinpath(filename)
    if os.path.exists(cache_file):
        jfrw = JsonFileRW(str(cache_file), LOGGER)
        return jfrw.read()
    else:
        return None

def store_history_days(history, instrument: Instrument, n_days: int):
    if instrument.timeframe.get_name() != '1-day':
        raise ValueError('Timeframe must be 1-day')
    make_cache_dir()
    symbol = instrument.symbol
    timeframe = instrument.timeframe.get_name()
    today = date.today().isoformat()
    filename = f'{symbol}_{timeframe}_{str(n_days)}_{today}.json'
    cache_file = HISTORY_CACHE_PATH.joinpath(filename)
    jfrw = JsonFileRW(str(cache_file), LOGGER)
    jfrw.write(history)
