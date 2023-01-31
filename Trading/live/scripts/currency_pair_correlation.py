from Trading.live.client.client import XTBLoggingClient
from Trading.instrument.instrument import Instrument
from Trading.config.config import USERNAME, PASSWORD, MODE
import logging
import pandas as pd

if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)

    n = 300
    usd_huf = client.get_last_n_candles_history(Instrument('USDHUF', '1D'), n)
    eur_usd = client.get_last_n_candles_history(Instrument('EURUSD', '1D'), n)

    usd_huf_oh = list(zip(usd_huf['open'], usd_huf['high']))
    eur_usd_oh = list(zip(eur_usd['open'], eur_usd['high']))


    usd_huf_open_price = usd_huf_oh[0][0]
    print("USD HUF OP", usd_huf_open_price)
    eur_usd_open_price = eur_usd_oh[0][0]
    print("EUR USD OP", eur_usd_open_price)

    min_total_profit = 1000
    max_total_profit = -1000

    for ((usd_huf_o, usd_huf_h), (eur_usd_o, eur_usd_h)) in zip(usd_huf_oh, eur_usd_oh):
        usdhuf_p = round(client.get_profit_calculation("USDHUF", usd_huf_open_price, usd_huf_h, 0.01, 1), 2)
        eurusd_p = round(client.get_profit_calculation("EURUSD", eur_usd_open_price, eur_usd_h, 0.01, 1), 2)
        total_profit = round(usdhuf_p + eurusd_p, 2)
        if total_profit > max_total_profit:
            max_total_profit = total_profit
        if total_profit < min_total_profit:
            min_total_profit = total_profit

        print(usdhuf_p, eurusd_p, total_profit)


    print(f"Min profit {min_total_profit}, Max profit {max_total_profit}")

    data = {"EURUSD" : eur_usd['open'], "USDHUF": usd_huf['open']}
    df = pd.DataFrame(data)
    correlation = df["EURUSD"].corr(df["USDHUF"])
    print(f"The correlation between EURUSD and USDHUF is {correlation}")

# volumes usdhuf, eurusd: 0.01, 0.01: Min profit -250.82, Max profit 416.43
# volumes usdhuf, eurusd: 0.01, 0.02: Min profit -315.63, Max profit 194.01
# for 300 days volumes usdhuf, eurusd: 0.01, 0.01: Min profit -1085, Max profit -53.56
