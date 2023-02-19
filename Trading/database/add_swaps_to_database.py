#!/usr/bin/python3
from Trading.config.config import DB_USERNAME, DB_PASSWORD, DB_NAME, DATA_STORAGE_PATH
from Trading.utils.write_to_file import read_json_file
import pymysql
from datetime import datetime


def add_swap(symbol, swap):
    # Open database connection
    db = pymysql.connect(host='localhost', database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)
    db.autocommit(True)
    # prepare a cursor object using cursor() method
    cursor = db.cursor()
    date_today = str(datetime.now().date())
    query = f"INSERT INTO trading.swaps(date_added, instrument, accumulated_swap) VALUES('{date_today}', '{symbol}', {swap});"
    cursor.execute(query)
    db.close()
