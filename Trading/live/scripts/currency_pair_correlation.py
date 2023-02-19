from Trading.live.client.client import XTBLoggingClient
from Trading.instrument.instrument import Instrument
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.utils.calculations import calculate_correlation, calculate_rolling_correlation
import logging
from Trading.utils.write_to_file import write_to_json_file, read_json_file
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from Trading.algo.indicators.indicator import BollingerBandsIndicator

N_CANDLES = 360
PAIR_1_SYMBOL = 'AUDUSD'
PAIR_2_SYMBOL = 'NZDUSD'
PAIR_1_POSITION = 'BUY'
PAIR_2_POSITION = 'SELL'
PAIR_1_VOLUME = 0.01
PAIR_2_VOLUME = 0.01

PAIR_1_MULTIPLIER = 1.5
PAIR_2_MULTIPLIER = 1


def get_cmd(position: str):
    if position == 'BUY':
        return 0
    else:
        return 1

def get_filename():
    return "data/hedging_correlation/" + PAIR_1_SYMBOL + "_" + PAIR_2_SYMBOL + ".json"

def get_prices_from_client(client, should_write_to_file=False):
    pair_1 = client.get_last_n_candles_history(Instrument(PAIR_1_SYMBOL, '1D'), N_CANDLES)
    pair_2 = client.get_last_n_candles_history(Instrument(PAIR_2_SYMBOL, '1D'), N_CANDLES)

    pair_1_oh = list(zip(pair_1['open'], pair_1['high']))
    pair_2_oh = list(zip(pair_2['open'], pair_2['high']))


    pair_1_open_price = pair_1_oh[0][0]
    print(f"{PAIR_1_SYMBOL} open price {pair_1_open_price}")
    pair_2_open_price = pair_2_oh[0][0]
    print(f"{PAIR_2_SYMBOL} open price {pair_2_open_price}")

    net_profits = list()
    pair_1_profits = list()
    pair_2_profits = list()
    i = 1
    for pair_1_o, pair_2_o in zip(pair_1['open'], pair_2['open']):
        pair_1_profit = client.get_profit_calculation(PAIR_1_SYMBOL, pair_1_open_price, pair_1_o, PAIR_1_VOLUME, get_cmd(PAIR_1_POSITION))
        pair_2_profit = client.get_profit_calculation(PAIR_2_SYMBOL, pair_2_open_price, pair_2_o, PAIR_2_VOLUME, get_cmd(PAIR_2_POSITION))
        print(f"Candles processed {i} / {N_CANDLES}")
        i += 1
        net_profits.append(pair_1_profit + pair_2_profit)
        pair_1_profits.append(pair_1_profit)
        pair_2_profits.append(pair_2_profit)

    if should_write_to_file:
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
                    'date': str(datetime.now().date())}
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


if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)

    #(pair_1_o, pair_2_o, net_profits) = get_prices_from_client(client, should_write_to_file=True)
    (pair_1_o, pair_2_o, net_profits) = get_prices_from_file()

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

    fig, ax = plt.subplots(3, figsize=(10, 5), sharex=True)
    ax[0].plot(net_profits, label=f'Hedged net profit', color='green')
    ax[1].plot(net_profits, label=f'Hedged net profit', color='orange')
    ax[2].plot(rolling_correlation, label=f'Rolling correlation', color='green')
    bb.plot(ax[1])

    ax[0].legend()
    ax[2].legend()

    ax[0].grid()
    ax[1].grid()
    ax[2].grid()

    ax[0].set_title(f'Hedged net profit for {PAIR_1_SYMBOL} {PAIR_1_POSITION} {PAIR_1_MULTIPLIER * PAIR_1_VOLUME} '
                    f'with {PAIR_2_SYMBOL} {PAIR_2_POSITION} {PAIR_2_MULTIPLIER * PAIR_2_VOLUME}')
    ax[1].set_title(f'Bollinger bands on hedged net profit')
    ax[0].set_xlabel('Days')
    ax[0].set_ylabel('Eur')

    ax[1].set_xlabel('Days')
    ax[1].set_ylabel('Eur')
    plt.show()
