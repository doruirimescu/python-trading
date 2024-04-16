from Trading.instrument.instrument import Instrument
from Trading.live.client.client import get_cmd, LoggingClient
from Trading.utils.write_to_file import read_json_file
from Trading.utils.custom_logging import get_logger
from Trading.config.config import DATA_STORAGE_PATH
from Trading.utils.calculations import calculate_net_profit_eur
from Trading.live.hedge.fixed_conversion_rates import convert_currency_to_eur
from functools import partial
from typing import List
from dataclasses import dataclass

MAIN_LOGGER = get_logger()


@dataclass
class PositionInfo:
    instrument: Instrument
    volume: int
    type: str
    multiplier: int
    open_prices:[]
    net_profits:[]

    def get_net_profits_with_multiplier(self):
        return [x * self.multiplier for x in self.net_profits]


def calculate_net_profit_with_multiplier_of_positions(positions: List[PositionInfo]):
    net_profits = [0] * len(positions[0].net_profits)
    for position in positions:
        net_profits = [x + y for x, y in zip(net_profits, position.get_net_profits_with_multiplier())]
    return net_profits


def get_returns_for_list_of_positions(
    client: LoggingClient,
    positions: List[PositionInfo],
    n_candles: int,
    should_reference_profits_to_zero=False,
):
    net_profits = [0] * n_candles
    dates = []

    for position in positions:
        instrument = position.instrument
        symbol = instrument.symbol
        volume = position.volume
        position_type = position.type
        multiplier = position.multiplier
        info = client.get_symbol(symbol)
        contract_value = volume * info["contractSize"]
        conversion_rate_eur = convert_currency_to_eur(info["currencyProfit"])

        profit_calculator = partial(
            calculate_net_profit_eur,
            contract_value=contract_value,
            quote_currency_to_eur_conversion_rate=conversion_rate_eur,
            cmd=get_cmd(position_type),
        )
        history = client.get_last_n_candles_history(instrument, n_candles)
        if not dates:
            dates = history["date"]

        open_price = 0
        if not should_reference_profits_to_zero:
            open_price = history["open"][0]
        pair_profits = list()

        for daily_open_price in history["open"]:
            profit = profit_calculator(
                open_price=open_price, close_price=daily_open_price
            )
            pair_profits.append(multiplier*profit)
        position.open_prices = history["open"]
        position.net_profits = pair_profits

        net_profits = [x + y for x, y in zip(net_profits, pair_profits)]

    data = {
        p.instrument.symbol: p.open_prices for p in positions
    }

    data["net_profits"] = net_profits
    data["N_DAYS"] = n_candles

    profits = {
        p.instrument.symbol + '_profits': p.net_profits for p in positions
    }
    data.update(profits)
    volumes = {
        p.instrument.symbol + '_volume': p.volume for p in positions
    }
    data.update(volumes)
    positions = {
        p.instrument.symbol + '_position': p.type for p in positions
    }
    data.update(positions)
    data['date'] = dates

    return data


def get_prices_from_client(
    client: LoggingClient,
    instrument_1: Instrument,
    instrument_2: Instrument,
    pair_1_volume: float,
    pair_2_volume: float,
    n_candles: int,
    pair_1_multiplier: float = 1.0,
    pair_2_multiplier: float = 1.0,
    pair_1_position: str = "BUY",
    pair_2_position: str = "SELL",
    should_reference_profits_to_zero=False,
    should_calculate_prices_with_client=True,
):
    pair_1_symbol = instrument_1.symbol
    pair_2_symbol = instrument_2.symbol

    if should_calculate_prices_with_client:
        pair_1_profit_calculator = partial(
            client.get_profit_calculation,
            symbol=pair_1_symbol,
            volume=pair_1_volume,
            cmd=get_cmd(pair_1_position),
        )
        pair_2_profit_calculator = partial(
            client.get_profit_calculation,
            symbol=pair_2_symbol,
            volume=pair_2_volume,
            cmd=get_cmd(pair_2_position),
        )
    else:
        info_1 = client.get_symbol(pair_1_symbol)
        info_2 = client.get_symbol(pair_2_symbol)
        pair_1_contract_value = pair_1_volume * info_1["contractSize"]
        pair_2_contract_value = pair_2_volume * info_2["contractSize"]
        pair_1_conversion_rate_eur = convert_currency_to_eur(info_1["currencyProfit"])
        pair_2_conversion_rate_eur = convert_currency_to_eur(info_2["currencyProfit"])

        pair_1_profit_calculator = partial(
            calculate_net_profit_eur,
            contract_value=pair_1_contract_value,
            quote_currency_to_eur_conversion_rate=pair_1_conversion_rate_eur,
            cmd=get_cmd(pair_1_position),
        )
        pair_2_profit_calculator = partial(
            calculate_net_profit_eur,
            contract_value=pair_2_contract_value,
            quote_currency_to_eur_conversion_rate=pair_2_conversion_rate_eur,
            cmd=get_cmd(pair_2_position),
        )

    pair_1 = client.get_last_n_candles_history(instrument_1, n_candles)
    pair_2 = client.get_last_n_candles_history(instrument_2, n_candles)

    pair_1_open_price, pair_2_open_price = 0, 0
    if not should_reference_profits_to_zero:
        pair_1_open_price = pair_1["open"][0]
        pair_2_open_price = pair_2["open"][0]
    MAIN_LOGGER.info(f"{pair_1_symbol} open price {pair_1_open_price}")
    MAIN_LOGGER.info(f"{pair_2_symbol} open price {pair_2_open_price}")

    net_profits = list()
    pair_1_profits = list()
    pair_2_profits = list()
    i = 1

    for pair_1_o, pair_2_o in zip(pair_1["open"], pair_2["open"]):
        pair_1_profit = pair_1_profit_calculator(
            open_price=pair_1_open_price, close_price=pair_1_o
        )
        pair_2_profit = pair_2_profit_calculator(
            open_price=pair_2_open_price, close_price=pair_2_o
        )

        net_profits.append(
            pair_1_multiplier * pair_1_profit + pair_2_multiplier * pair_2_profit
        )
        pair_1_profits.append(pair_1_profit)
        pair_2_profits.append(pair_2_profit)
        MAIN_LOGGER.info(f"Candles processed {i} / {n_candles}")
        i += 1

    prices = {
        pair_1_symbol: pair_1["open"],
        pair_2_symbol: pair_2["open"],
        "net_profits": net_profits,
        pair_1_symbol + "_profits": pair_1_profits,
        pair_2_symbol + "_profits": pair_2_profits,
        pair_1_symbol + "_volume": pair_1_volume,
        pair_2_symbol + "_volume": pair_2_volume,
        pair_1_symbol + "_position": pair_1_position,
        pair_2_symbol + "_position": pair_2_position,
        "N_DAYS": n_candles,
        "dates": pair_1["date"],
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
    for p1, p2 in zip(
        json_dict[pair_1_symbol + "_profits"], json_dict[pair_2_symbol + "_profits"]
    ):
        net_profits.append(pair_1_multiplier * p1 + pair_2_multiplier * p2)

    pair_1_open_price = pair_1_o[0]
    pair_2_open_price = pair_2_o[0]

    MAIN_LOGGER.info(f"{pair_1_symbol} open price {pair_1_open_price}")
    MAIN_LOGGER.info(f"{pair_2_symbol} open price {pair_2_open_price}")

    return (pair_1_o, pair_2_o, net_profits)


def get_filename(pair_1_symbol: str, pair_2_symbol: str, extra: str = ""):
    return f"{DATA_STORAGE_PATH}hedging_correlation/{pair_1_symbol}_{pair_2_symbol}{extra}.json"


def normalize_zero_referenced_profits(zero_referenced_profits: List[float]):
    first_profit = zero_referenced_profits[0]
    normalized_zero_data = [p - first_profit for p in zero_referenced_profits]
    return normalized_zero_data
