from Trading.live.client.client import XTBLoggingClient
from Trading.instrument.instrument import Instrument
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.utils.calculations import calculate_correlation, calculate_rolling_correlation
from Trading.utils.time import get_datetime_now_cet
from Trading.config.config import TIMEZONE
import pytz
import datetime

import logging
from Trading.utils.write_to_file import write_to_json_file, read_json_file
# from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from Trading.algo.indicators.indicator import BollingerBandsIndicator
import sys

N_CANDLES = 360
PAIR_1_SYMBOL = 'AUDUSD'
PAIR_2_SYMBOL = 'NZDUSD'
PAIR_1_POSITION = 'BUY'
PAIR_2_POSITION = 'SELL'
PAIR_1_VOLUME = 0.01
PAIR_2_VOLUME = 0.01

PAIR_1_MULTIPLIER = 1
PAIR_2_MULTIPLIER = 2

FROM_CLIENT      = False
SAVE_TO_FILE     = False

if FROM_CLIENT:
    PAIR_1_MULTIPLIER, PAIR_2_MULTIPLIER = 1, 1

def exit():
    sys.exit(0)

def get_cmd(position: str):
    if position == 'BUY':
        return 0
    else:
        return 1

def get_filename():
    return "data/hedging_correlation/" + PAIR_1_SYMBOL + "_" + PAIR_2_SYMBOL + ".json"

def add_missing_candles_to_existing_json():
    filename = get_filename()
    json_dict = read_json_file(filename)
    today_date = get_datetime_now_cet()
    last_date_in_dict = datetime.datetime.strptime(json_dict['dates'][-1], "%Y-%m-%d %H:%M:%S")
    last_date_in_dict_no_timezone = last_date_in_dict
    last_date_in_dict = pytz.timezone(TIMEZONE).localize(last_date_in_dict)

    days_behind = (today_date - last_date_in_dict).days

    if days_behind <= 0:
        return

    pair_1 = client.get_last_n_candles_history(Instrument(PAIR_1_SYMBOL, '1D'), days_behind)
    pair_2 = client.get_last_n_candles_history(Instrument(PAIR_2_SYMBOL, '1D'), days_behind)

    pair_1_open_price = json_dict[PAIR_1_SYMBOL][0]
    pair_2_open_price = json_dict[PAIR_2_SYMBOL][0]
    net_profits = list()
    pair_1_profits = list()
    pair_2_profits = list()
    i = 1
    for pair_1_o, pair_2_o in zip(pair_1['open'], pair_2['open']):
        pair_1_profit = client.get_profit_calculation(PAIR_1_SYMBOL, pair_1_open_price, pair_1_o, PAIR_1_VOLUME, get_cmd(PAIR_1_POSITION))
        pair_2_profit = client.get_profit_calculation(PAIR_2_SYMBOL, pair_2_open_price, pair_2_o, PAIR_2_VOLUME, get_cmd(PAIR_2_POSITION))
        net_profits.append(pair_1_profit + pair_2_profit)
        pair_1_profits.append(pair_1_profit)
        pair_2_profits.append(pair_2_profit)
        print(f"Candles processed {i} / {days_behind}")
        i += 1

    print(last_date_in_dict_no_timezone)
    if last_date_in_dict_no_timezone == pair_1['date'][0]:
        print("POPPING")
        pair_1['open'].pop()
        pair_2['open'].pop()
        net_profits.pop()
        json_dict[PAIR_1_SYMBOL + "_profits"].pop()
        json_dict[PAIR_2_SYMBOL + "_profits"].pop()
        json_dict['dates'].pop()
        days_behind -= 1

    json_dict[PAIR_1_SYMBOL] += pair_1['open']
    json_dict[PAIR_2_SYMBOL] += pair_2['open']
    json_dict['net_profits'] += net_profits
    json_dict[PAIR_1_SYMBOL + "_profits"] += pair_1_profits
    json_dict[PAIR_2_SYMBOL + "_profits"] += pair_2_profits
    json_dict['N_DAYS'] = int(json_dict['N_DAYS']) + days_behind
    json_dict['dates'] += pair_1['date']

    write_to_json_file(get_filename(), json_dict)
    exit()

def get_prices_from_client(client):
    pair_1 = client.get_last_n_candles_history(Instrument(PAIR_1_SYMBOL, '1D'), N_CANDLES)
    pair_2 = client.get_last_n_candles_history(Instrument(PAIR_2_SYMBOL, '1D'), N_CANDLES)


    pair_1_open_price = pair_1['open'][0]
    print(f"{PAIR_1_SYMBOL} open price {pair_1_open_price}")
    pair_2_open_price = pair_2['open'][0]
    print(f"{PAIR_2_SYMBOL} open price {pair_2_open_price}")

    net_profits = list()
    pair_1_profits = list()
    pair_2_profits = list()
    i = 1
    for pair_1_o, pair_2_o in zip(pair_1['open'], pair_2['open']):
        pair_1_profit = client.get_profit_calculation(PAIR_1_SYMBOL, pair_1_open_price, pair_1_o, PAIR_1_VOLUME, get_cmd(PAIR_1_POSITION))
        pair_2_profit = client.get_profit_calculation(PAIR_2_SYMBOL, pair_2_open_price, pair_2_o, PAIR_2_VOLUME, get_cmd(PAIR_2_POSITION))
        i += 1
        net_profits.append(pair_1_profit + pair_2_profit)
        pair_1_profits.append(pair_1_profit)
        pair_2_profits.append(pair_2_profit)

    if SAVE_TO_FILE:
        prices = {  PAIR_1_SYMBOL: pair_1['open'],
                    PAIR_2_SYMBOL: pair_2['open'],
                    'net_profits': net_profits,
                    PAIR_1_SYMBOL + "_profits": pair_1_profits,
                    PAIR_2_SYMBOL + "_profits": pair_2_profits,
                    PAIR_1_SYMBOL + "_volume" : PAIR_1_VOLUME,
                    PAIR_2_SYMBOL + "_volume" : PAIR_2_VOLUME,
                    PAIR_1_SYMBOL + "_position": PAIR_1_POSITION,
                    PAIR_2_SYMBOL + "_position": PAIR_2_POSITION,
                    'N_DAYS': N_CANDLES,
                    'dates': pair_1['date']}
        write_to_json_file(get_filename(), prices)


    return (pair_1['open'], pair_2['open'], net_profits)


def get_prices_from_file():
    filename = get_filename()
    json_dict = read_json_file(filename)
    pair_1_o = json_dict[PAIR_1_SYMBOL]
    pair_2_o = json_dict[PAIR_2_SYMBOL]
    net_profits = list()
    for p1, p2 in  zip(json_dict[PAIR_1_SYMBOL + "_profits"], json_dict[PAIR_2_SYMBOL + "_profits"]):
        net_profits.append(PAIR_1_MULTIPLIER * p1 + PAIR_2_MULTIPLIER * p2)

    pair_1_open_price = pair_1_o[0]
    print(f"{PAIR_1_SYMBOL} open price {pair_1_open_price}")
    pair_2_open_price = pair_2_o[0]
    print(f"{PAIR_2_SYMBOL} open price {pair_2_open_price}")

    return (pair_1_o, pair_2_o, net_profits)


def count_zero_crossings(net_profits):
    n = 0
    for i, j in zip(net_profits, net_profits[1:]):
        if i*j <= 0:
            n += 1
    return n

def convert_ron_to_eur(net_profits):
    """Profit calculations coming from client are in RON, because the demo account is in RON.
    Thus, before presenting, we need to convert in eur
    """
    eur_ron = float(client.get_current_price('EURRON')[0])
    print(eur_ron)
    return [float(n)/eur_ron for n in net_profits]

if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)
    add_missing_candles_to_existing_json()

    if FROM_CLIENT:
        (pair_1_o, pair_2_o, net_profits) = get_prices_from_client(client)
    else:
        (pair_1_o, pair_2_o, net_profits) = get_prices_from_file()

    net_profits = convert_ron_to_eur(net_profits)

    avg_net = sum(net_profits) / len(net_profits)
    print(f"Average net profit: {avg_net}")
    correlation = calculate_correlation(PAIR_1_SYMBOL, PAIR_2_SYMBOL,
                                        pair_1_o, pair_2_o)

    # Prepare net profits for bollinger bands
    main_data = pd.DataFrame({'close': net_profits})
    bb = BollingerBandsIndicator(20)
    bb.calculate_bb(main_data)

    rolling_correlation = calculate_rolling_correlation(PAIR_1_SYMBOL,
                                                        PAIR_2_SYMBOL,
                                                        pair_1_o,
                                                        pair_2_o,
                                                        20)

    print(f"Crossed zero {count_zero_crossings(net_profits)} times")

    fig, ax = plt.subplots(3, figsize=(10, 5), sharex=True)
    ax[0].plot(net_profits, label=f'Hedged net profit', color='green')

    ax[1].plot(net_profits, label=f'Hedged net profit', color='orange')
    bb.plot(ax[1])
    ax[1].set_title(f'Bollinger bands on hedged net profit')
    ax[1].set_xlabel('Days')
    ax[1].set_ylabel('Eur')
    ax[1].grid()

    ax[0].axhline(color='red')

    ax[0].legend()
    ax[0].grid()
    ax[0].set_title(f'Hedged net profit for {PAIR_1_SYMBOL} {PAIR_1_POSITION} {PAIR_1_MULTIPLIER * PAIR_1_VOLUME} '
                    f'with {PAIR_2_SYMBOL} {PAIR_2_POSITION} {PAIR_2_MULTIPLIER * PAIR_2_VOLUME}')
    ax[0].set_xlabel('Days')
    ax[0].set_ylabel('Eur')
    ax[0].tick_params(labelbottom=True)

    ax[2].plot(rolling_correlation, label=f'Rolling correlation', color='green')
    ax[2].legend()
    ax[2].grid()

    plt.show()
