#!/usr/bin/python3
from Trading.config.config import DB_USERNAME, DB_PASSWORD, DB_NAME, DATA_STORAGE_PATH
from Trading.utils.write_to_file import read_json_file
import pymysql


PAIR_1_SYMBOL = 'AUDUSD'
PAIR_2_SYMBOL = 'NZDUSD'

#TODO: aggregate all those methods in a package called hedging
filename = DATA_STORAGE_PATH + "hedging_correlation/" + PAIR_1_SYMBOL + "_" + PAIR_2_SYMBOL + ".json"

json_dict = read_json_file(filename)
i_1_o = json_dict[PAIR_1_SYMBOL]
i_2_o = json_dict[PAIR_2_SYMBOL]
i_1_profits = json_dict[PAIR_1_SYMBOL + "_profits"]
i_2_profits = json_dict[PAIR_2_SYMBOL + "_profits"]
dates = json_dict['dates']

# Open database connection
db = pymysql.connect(host='localhost', database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)
db.autocommit(True)
# prepare a cursor object using cursor() method
cursor = db.cursor()

# delete today
query = "DELETE FROM trading.hedge_monitor WHERE date_open <= CURRENT_DATE"
cursor.execute(query)

for (date_open,
     i_1_open_price,
     i_2_open_price,
     i_1_net_profits,
     i_2_net_profits) in zip(dates, i_1_o, i_2_o, i_1_profits, i_2_profits):
    query = (
        f"INSERT INTO trading.hedge_monitor(date_open, instrument_1_symbol, instrument_2_symbol, "
        f"instrument_1_open_price, instrument_2_open_price, instrument_1_net_profits, instrument_2_net_profits) VALUES ("
        f"'{date_open}', '{PAIR_1_SYMBOL}', '{PAIR_2_SYMBOL}', {i_1_open_price}, {i_2_open_price}, {i_1_net_profits}, {i_2_net_profits});"
        )
    print(query)
    cursor.execute(query)


# disconnect from server
db.close()
