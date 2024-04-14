from Trading.live.client.client import XTBTradingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.instrument import Instrument, Timeframe
from dotenv import load_dotenv
from Trading.utils.write_to_file import write_to_json_file, read_json_file
from Trading.utils.calculations import calculate_net_profit_eur
from Trading.live.hedge.fixed_conversion_rates import convert_currency_to_eur

import time
import os
import logging
from Trading.live.hedge.data import get_prices_from_client, get_filename
import sys
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

def exit():
    sys.exit(0)

@dataclass
class DayResult:
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    date: Optional[float] = None
    hour_low: Optional[int] = None
    hour_high: Optional[int] = None


if __name__ == '__main__':
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    SYMBOL = 'NATGAS'
    N_DAYS = 200
    history_days = client.get_last_n_candles_history(Instrument(SYMBOL, Timeframe('1D')), N_DAYS)
    history_hours = client.get_last_n_candles_history(Instrument(SYMBOL, Timeframe('1h')), 24*N_DAYS)


    days_dict: Dict[date, DayResult] = dict()
    all_hours_high = list()
    all_hours_low = list()

    for o, h, l, c, d in zip(history_days['open'], history_days['high'], history_days['low'],
                             history_days['close'], history_days['date']):
        day_result = DayResult()
        day_result.open = o
        day_result.high = h
        day_result.low = l
        day_result.close = c
        date = d.date()
        day_result.date = date
        days_dict[date] = day_result

    print(days_dict.keys())
    for o, h, l, c, d in zip(history_hours['open'], history_hours['high'], history_hours['low'],
                             history_hours['close'], history_hours['date']):
        date = d.date()
        if days_dict.get(date):
            if days_dict[date].high == h:
                days_dict[date].hour_high = d.hour
                all_hours_high.append(d.hour)
            elif days_dict[date].low == l:
                days_dict[date].hour_low = d.hour
                all_hours_low.append(d.hour)

    print(days_dict)

    import matplotlib.pyplot as plt
    import numpy as np
    bins = [i/2.0 for i in range(48)]
    fig, ax = plt.subplots(2, figsize=(10, 5), sharex=True)

    all_hours_max = all_hours_low + all_hours_high

    n, bins, patches = ax[0].hist(all_hours_high, bins=bins, align='mid')
    ax[0].set_xticks([i for i in range(24)])
    ax[0].set_title(f'{SYMBOL} hours high last {N_DAYS} days')
    ax[0].tick_params(labelbottom=True)


    n, bins, patches = ax[1].hist(all_hours_low, bins=bins, align='mid')
    ax[1].set_xticks([i for i in range(24)])
    ax[1].set_title(f'{SYMBOL} hours low last {N_DAYS} days')

    plt.show()
