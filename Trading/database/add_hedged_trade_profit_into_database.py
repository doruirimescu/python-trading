#!/usr/bin/python3
from Trading.config.config import DB_USERNAME, DB_PASSWORD, DB_NAME, DATA_STORAGE_PATH
import pymysql


def add_hedged_profit(trade_name, net_profit):
    # Open database connection
    db = pymysql.connect(host='localhost', database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)
    db.autocommit(True)
    # prepare a cursor object using cursor() method
    cursor = db.cursor()
    query = f"DELETE FROM trading.hedged_profit WHERE trade_name='{trade_name}';"
    cursor.execute(query)

    query = (
        f"INSERT INTO trading.hedged_profit(trade_name, net_profit) VALUES ('{trade_name}', {net_profit});"
        )
    cursor.execute(query)
    db.close()
