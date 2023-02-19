#!/usr/bin/python3
from Trading.config.config import DB_USERNAME, DB_PASSWORD, DB_NAME, DATA_STORAGE_PATH
import pymysql


def add_hedge(date_open, instrument_1_symbol, instrument_2_symbol,
              instrument_1_open_price, instrument_2_open_price,
              instrument_1_net_profits, instrument_2_net_profits):
    # Open database connection
    db = pymysql.connect(host='localhost', database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)
    db.autocommit(True)
    # prepare a cursor object using cursor() method
    cursor = db.cursor()

    query = (
        f"INSERT INTO trading.hedge_monitor(date_open, instrument_1_symbol, instrument_2_symbol, "
        f"instrument_1_open_price, instrument_2_open_price, instrument_1_net_profits, instrument_2_net_profits) VALUES ("
        f"'{date_open}', '{instrument_1_symbol}', '{instrument_2_symbol}', {instrument_1_open_price}, {instrument_2_open_price}, {instrument_1_net_profits}, {instrument_2_net_profits});"
        )
    cursor.execute(query)
    db.close()
