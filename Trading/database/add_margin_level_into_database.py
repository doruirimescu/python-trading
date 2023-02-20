#!/usr/bin/python3
from Trading.config.config import DB_USERNAME, DB_PASSWORD, DB_NAME, DATA_STORAGE_PATH
import pymysql


def add_margin_level(balance, margin, equity, margin_free, margin_level, stock_value):
    # Open database connection
    db = pymysql.connect(host='localhost', database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)
    db.autocommit(True)
    # prepare a cursor object using cursor() method
    cursor = db.cursor()

    # First delete
    query = f"DELETE FROM trading.margin_level WHERE id=1;"
    cursor.execute(query)

    query = (
        f"INSERT INTO trading.margin_level(balance, margin, equity, margin_free, margin_level, stock_value) VALUES"
        f" ({balance}, {margin}, {equity}, {margin_free}, {margin_level}, {stock_value});"
        )
    cursor.execute(query)
    db.close()
