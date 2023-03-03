from Trading.instrument.instrument import Instrument
from Trading.live.client.client import get_cmd, LoggingClient
from Trading.config.config import DATA_STORAGE_PATH
from Trading.utils.write_to_file import write_to_json_file, read_json_file
from typing import List


def get_prices_from_client(client: LoggingClient,
                           instrument_1: Instrument,
                           instrument_2: Instrument,
                           pair_1_volume: float,
                           pair_2_volume: float,
                           n_candles: int,
                           should_reference_profits_to_zero=True):
    pair_1_symbol = instrument_1.symbol
    pair_2_symbol = instrument_2.symbol

    pair_1 = client.get_last_n_candles_history(instrument_1, n_candles)
    pair_2 = client.get_last_n_candles_history(instrument_2, n_candles)

    pair_1_open_price, pair_2_open_price = 0, 0
    if not should_reference_profits_to_zero:
        pair_1_open_price = pair_1['open'][0]
        pair_2_open_price = pair_2['open'][0]
    print(f"{pair_1_symbol} open price {pair_1_open_price}")
    print(f"{pair_2_symbol} open price {pair_2_open_price}")

    net_profits = list()
    pair_1_profits = list()
    pair_2_profits = list()
    i = 1
    client.login()
    for pair_1_o, pair_2_o in zip(pair_1['open'], pair_2['open']):
        pair_1_profit = client.get_profit_calculation(
            pair_1_symbol, pair_1_open_price, pair_1_o, pair_1_volume, get_cmd('BUY')
            )
        pair_2_profit = client.get_profit_calculation(
            pair_2_symbol, pair_2_open_price, pair_2_o, pair_2_volume, get_cmd('SELL')
            )

        net_profits.append(pair_1_profit + pair_2_profit)
        pair_1_profits.append(pair_1_profit)
        pair_2_profits.append(pair_2_profit)
        print(f"Candles processed {i} / {n_candles}")
        i += 1
    client.logout()
    prices = {
        pair_1_symbol: pair_1['open'],
        pair_2_symbol: pair_2['open'],
        'net_profits': net_profits,
        pair_1_symbol + "_profits": pair_1_profits,
        pair_2_symbol + "_profits": pair_2_profits,
        pair_1_symbol + "_volume" : pair_1_volume,
        pair_2_symbol + "_volume" : pair_2_volume,
        pair_1_symbol + "_position": 'BUY',
        pair_2_symbol + "_position": 'SELL',
        'N_DAYS': n_candles,
        'dates': pair_1['date']
        }

    return prices


def get_prices_from_file(
    pair_1_symbol: str,
    pair_2_symbol: str,
    pair_1_multiplier: float,
    pair_2_multiplier: float,
    ):
    filename = get_filename(pair_1_symbol, pair_2_symbol)
    json_dict = read_json_file(filename)
    pair_1_o = json_dict[pair_1_symbol]
    pair_2_o = json_dict[pair_2_symbol]
    net_profits = list()
    for p1, p2 in  zip(json_dict[pair_1_symbol + "_profits"], json_dict[pair_2_symbol + "_profits"]):
        net_profits.append(pair_1_multiplier * p1 + pair_2_multiplier * p2)

    pair_1_open_price = pair_1_o[0]
    print(f"{pair_1_symbol} open price {pair_1_open_price}")
    pair_2_open_price = pair_2_o[0]
    print(f"{pair_2_symbol} open price {pair_2_open_price}")

    return (pair_1_o, pair_2_o, net_profits)


def get_filename(
        pair_1_symbol: str,
        pair_2_symbol: str,
        extra: str = ""
        ):
    return f"{DATA_STORAGE_PATH}hedging_correlation/{pair_1_symbol}_{pair_2_symbol}{extra}.json"


def normalize_zero_referenced_profits(zero_referenced_profits: List[float]):
    first_profit = zero_referenced_profits[0]
    normalized_zero_data = [p - first_profit for p in zero_referenced_profits]
    return normalized_zero_data
