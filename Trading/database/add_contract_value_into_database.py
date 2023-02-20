#!/usr/bin/python3
from Trading.config.config import DB_USERNAME, DB_PASSWORD, DB_NAME, DATA_STORAGE_PATH
import pymysql


def add_contract_value(symbol, value):
    # Open database connection
    db = pymysql.connect(host='localhost', database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)
    db.autocommit(True)
    # prepare a cursor object using cursor() method
    cursor = db.cursor()

    # First delete
    query = f"DELETE FROM trading.contract_value WHERE symbol='{symbol}';"
    cursor.execute(query)

    query = (
        f"INSERT INTO trading.contract_value(symbol, contract_value) VALUES ('{symbol}', {value});"
        )
    cursor.execute(query)
    db.close()
