from Trading.live.client.client import XTBLoggingClient, get_cmd
from Trading.instrument import Instrument, Timeframe
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.utils.calculations import (
    count_zero_crossings,
)
from Trading.utils.custom_logging import get_logger
from Trading.utils.time import get_datetime_now_cet
from Trading.config.config import TIMEZONE
from Trading.live.hedge.data import (
    get_filename,
    calculate_net_profit_with_multiplier_of_positions,
    PositionInfo,
    get_returns_for_list_of_positions,
)
from matplotlib.widgets import Slider, Button, RadioButtons

import pytz
import datetime

from Trading.utils.write_to_file import write_to_json_file, read_json_file

# from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from Trading.algo.indicators.indicator import BollingerBandsIndicator
import sys


def exit():
    sys.exit(0)


#! Use percentage of the initial price as return. In this way, both net profits are
#! already normalized

N_CANDLES = 4000
PAIR_1_SYMBOL = "NZDUSD"
PAIR_2_SYMBOL = "AUDUSD"
PAIR_1_POSITION = "BUY"
PAIR_2_POSITION = "SELL"
PAIR_1_VOLUME = 1
PAIR_2_VOLUME = 1

PAIR_1_MULTIPLIER = 1
PAIR_2_MULTIPLIER = 1

SLIDER_MIN = 1
SLIDER_MAX = 5
SLIDER_STEP = 0.1

FILENAME = get_filename(PAIR_1_SYMBOL, PAIR_2_SYMBOL)


positions = [
    # PositionInfo(
    #     instrument=Instrument(PAIR_1_SYMBOL, "1D"),
    #     volume=PAIR_1_VOLUME,
    #     type=PAIR_1_POSITION,
    #     multiplier=PAIR_1_MULTIPLIER,
    #     open_prices=[],
    #     net_profits=[],
    # ),
    # PositionInfo(
    #     instrument=Instrument(PAIR_2_SYMBOL, "1D"),
    #     volume=PAIR_2_VOLUME,
    #     type=PAIR_2_POSITION,
    #     multiplier=PAIR_2_MULTIPLIER,
    #     open_prices=[],
    #     net_profits=[],
    # ),

    #! Do not delete !
    # Fluctuate around 0
    # SHY.US_5 6 BUY, IEF.US_5 2 SELL
    # IBTE.UK BUY 111, IEF.US_5 SELL 6 or BUY 77.7 with SELL 1.6

    # Perfect ascending trend:
    # IBTA.UK 15 BUY, IEF.US_5 1 SELL
    PositionInfo(
        instrument=Instrument("INTC.US_9", Timeframe("1D")),
        volume=1,
        type="BUY",
        multiplier=1,
        open_prices=[],
        net_profits=[],
    ),
    PositionInfo(
        instrument=Instrument("AMD.US_9", Timeframe("1D")),
        volume=1,
        type="SELL",
        multiplier=1,
        open_prices=[],
        net_profits=[],
    ),

    # PositionInfo(
    #     instrument=Instrument("AUDNZD", "1D"),
    #     volume=1,
    #     type="SELL",
    #     multiplier=1,
    #     open_prices=[],
    #     net_profits=[],
    # ),
]


def add_missing_candles_to_existing_json():
    json_dict = read_json_file(FILENAME)
    if not json_dict:
        return
    today_date = get_datetime_now_cet()
    last_date_in_dict = datetime.datetime.strptime(
        json_dict["dates"][-1], "%Y-%m-%d %H:%M:%S"
    )
    last_date_in_dict_no_timezone = last_date_in_dict
    last_date_in_dict = pytz.timezone(TIMEZONE).localize(last_date_in_dict)

    days_behind = (today_date - last_date_in_dict).days

    if days_behind <= 0:
        return

    pair_1 = client.get_last_n_candles_history(
        Instrument(PAIR_1_SYMBOL, Timeframe("1D")), days_behind
    )
    pair_2 = client.get_last_n_candles_history(
        Instrument(PAIR_2_SYMBOL, Timeframe("1D")), days_behind
    )

    pair_1_open_price = json_dict[PAIR_1_SYMBOL][0]
    pair_2_open_price = json_dict[PAIR_2_SYMBOL][0]
    net_profits = list()
    pair_1_profits = list()
    pair_2_profits = list()
    i = 1
    for pair_1_o, pair_2_o in zip(pair_1["open"], pair_2["open"]):
        pair_1_profit = client.get_profit_calculation(
            PAIR_1_SYMBOL,
            pair_1_open_price,
            pair_1_o,
            PAIR_1_VOLUME,
            get_cmd(PAIR_1_POSITION),
        )
        pair_2_profit = client.get_profit_calculation(
            PAIR_2_SYMBOL,
            pair_2_open_price,
            pair_2_o,
            PAIR_2_VOLUME,
            get_cmd(PAIR_2_POSITION),
        )
        net_profits.append(pair_1_profit + pair_2_profit)
        pair_1_profits.append(pair_1_profit)
        pair_2_profits.append(pair_2_profit)
        MAIN_LOGGER.info(f"Candles processed {i} / {days_behind}")
        i += 1

    MAIN_LOGGER.info(last_date_in_dict_no_timezone)
    if last_date_in_dict_no_timezone == pair_1["date"][0]:
        MAIN_LOGGER.info("POPPING")
        pair_1["open"].pop()
        pair_2["open"].pop()
        net_profits.pop()
        json_dict[PAIR_1_SYMBOL + "_profits"].pop()
        json_dict[PAIR_2_SYMBOL + "_profits"].pop()
        json_dict["dates"].pop()
        days_behind -= 1

    json_dict[PAIR_1_SYMBOL] += pair_1["open"]
    json_dict[PAIR_2_SYMBOL] += pair_2["open"]
    json_dict["net_profits"] += net_profits
    json_dict[PAIR_1_SYMBOL + "_profits"] += pair_1_profits
    json_dict[PAIR_2_SYMBOL + "_profits"] += pair_2_profits
    json_dict["N_DAYS"] = int(json_dict["N_DAYS"]) + days_behind
    json_dict["dates"] += pair_1["date"]

    write_to_json_file(FILENAME, json_dict)
    exit()


def convert_ron_to_eur(net_profits):
    """Profit calculations coming from client are in RON, because the demo account is in RON.
    Thus, before presenting, we need to convert in eur
    """
    eur_ron = float(client.get_current_price("EURRON")[0])
    MAIN_LOGGER.info(eur_ron)
    return [float(n) / eur_ron for n in net_profits]


def plot_main(main_ax, positions, main_fig):

    for ax in main_ax:
        ax.cla()

    net_profits = calculate_net_profit_with_multiplier_of_positions(positions)
    avg_net = sum(net_profits) / len(net_profits)
    MAIN_LOGGER.info(f"Average net profit: {avg_net}")

    main_ax[0].plot(net_profits, label=f"Hedged net profit", color="green")
    main_ax[0].axhline(color="red", y=avg_net)

    main_ax[0].legend()
    main_ax[0].grid()

    txt = ""
    for position in positions:
        txt += position.instrument.symbol
        txt += " "
        txt += str(position.type) + " "
        txt += str(position.volume * position.multiplier) + " "
        txt += "with "
    txt = txt[:-6]

    main_ax[0].set_title(f"Hedged net profit for {txt} \nentered N {N_CANDLES} days ago")
    main_ax[0].set_xlabel("Days")
    main_ax[0].set_ylabel("Eur")
    main_ax[0].tick_params(labelbottom=True)

    # Prepare different colors
    colors = ["red", "blue", "green", "orange", "purple", "black"]
    for i, position in enumerate(positions):
        main_ax[1 + i].plot(
            position.get_net_profits_with_multiplier(),
            label=f"{position.instrument.symbol} profit",
            color=colors[i],
        )
        main_ax[1 + i].legend()
        main_ax[1 + i].grid()
    main_fig.canvas.draw()

if __name__ == "__main__":
    MAIN_LOGGER = get_logger()

    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)
    # add_missing_candles_to_existing_json()

    data = get_returns_for_list_of_positions(client, positions, N_CANDLES)
    net_profits = data["net_profits"]

    # Prepare net profits for bollinger bands
    main_data = pd.DataFrame({"close": net_profits})
    bb = BollingerBandsIndicator(20)
    bb.calculate_bb(main_data)

    MAIN_LOGGER.info(f"Crossed zero {count_zero_crossings(net_profits)} times")

    for p in positions:
        MAIN_LOGGER.info(f"Open price of {p.instrument.symbol}: {p.open_prices[0]}")

    main_fig, main_ax = plt.subplots(1 + len(positions), figsize=(10, 5), sharex=True)
    plot_main(main_ax, positions, main_fig)

    fig = plt.figure(figsize=(10, 5))
    sliders = []
    for i, position in enumerate(positions):
        sliders.append(
            Slider(
                plt.axes([0.25, 0.2 + i * 0.2, 0.5, 0.03]),
                f"{position.instrument.symbol} multiplier",
                SLIDER_MIN,
                SLIDER_MAX,
                valinit=position.multiplier,
                valstep=SLIDER_STEP,
                dragging=True,
            )
        )

        def update(val, index=i):
            print(f"---- Updating with value {val}----")
            positions[index].multiplier = val
            plot_main(main_ax, positions, main_fig)
            for p in positions:
                print(f"{p.instrument.symbol} multiplier: {p.multiplier}")
        sliders[i].on_changed(update)

    # create another plot for bollinger bands
    fig, ax = plt.subplots(1, figsize=(10, 5), sharex=True)
    ax.plot(net_profits, label=f"Hedged net profit", color="orange")
    bb.plot(ax)
    ax.set_title(f"Bollinger bands on hedged net profit")
    ax.set_xlabel("Days")
    ax.set_ylabel("Eur")
    ax.grid()
    # add slider for bollinger bands
    ax_bb = plt.axes([0.25, 0.1, 0.65, 0.03])
    plt.show()


# ETFS:
# wisdomtree industrial metals AIGI.UK
