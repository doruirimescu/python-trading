from Trading.live.client.client import XTBLoggingClient
from Trading.instrument.instrument import Instrument
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.utils.calculations import calculate_correlation, calculate_rolling_correlation
import logging
from Trading.database.add_hedge_into_database import add_hedge
from Trading.utils.write_to_file import read_json_file

PAIR_1_SYMBOL = 'AUDUSD'
PAIR_2_SYMBOL = 'NZDUSD'
PAIR_1_POSITION = 'BUY'
PAIR_2_POSITION = 'SELL'
PAIR_1_VOLUME = 0.01
PAIR_2_VOLUME = 0.01



def get_cmd(position: str):
    if position == 'BUY':
        return 0
    else:
        return 1

def get_filename():
    return "data/hedging_correlation/" + PAIR_1_SYMBOL + "_" + PAIR_2_SYMBOL + ".json"


def get_prices_from_file():
    filename = get_filename()
    json_dict = read_json_file(filename)
    pair_1_o = json_dict[PAIR_1_SYMBOL]
    pair_2_o = json_dict[PAIR_2_SYMBOL]
    net_profits = list()

    pair_1_open_price = pair_1_o[0]
    print(f"{PAIR_1_SYMBOL} open price {pair_1_open_price}")
    pair_2_open_price = pair_2_o[0]
    print(f"{PAIR_2_SYMBOL} open price {pair_2_open_price}")

    return (pair_1_open_price, pair_2_open_price)


if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)

    (pair_1_opening_price, pair_2_opening_price) = get_prices_from_file()

    pair_1_open_today = client.get_last_n_candles_history(Instrument(PAIR_1_SYMBOL, '1D'), 1)['open'][0]
    pair_2_open_today = client.get_last_n_candles_history(Instrument(PAIR_2_SYMBOL, '1D'), 1)['open'][0]
    date_open = client.get_last_n_candles_history(Instrument(PAIR_1_SYMBOL, '1D'), 1)['date'][0]
    print(date_open)

    pair_1_profit = client.get_profit_calculation(PAIR_1_SYMBOL, pair_1_opening_price, pair_1_open_today, PAIR_1_VOLUME, get_cmd(PAIR_1_POSITION))
    pair_2_profit = client.get_profit_calculation(PAIR_2_SYMBOL, pair_2_opening_price, pair_2_open_today, PAIR_2_VOLUME, get_cmd(PAIR_2_POSITION))
    try:
        add_hedge(date_open, PAIR_1_SYMBOL, PAIR_2_SYMBOL, pair_1_open_today, pair_2_open_today, pair_1_profit, pair_2_profit)
    except Exception as e:
        print(e)
