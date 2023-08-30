#!/usr/bin/python3
from Trading.config.config import DB_USERNAME, DB_PASSWORD, DB_NAME, DATA_STORAGE_PATH
import pymysql
from enum import Enum


class StockInstrumentType(str, Enum):
    STOCK = "STC"
    ETF = "ETF"

    def is_valid(self, value: str):
        return value in set(item.value for item in StockInstrumentType)


class StockAccountType(str, Enum):
    EUR = "EUR"
    USD = "USD"


def add_stock_value(symbol: str,
                    instrument_type: StockInstrumentType,
                    contract_value: float,
                    profit: float,
                    account_type: StockAccountType):
    db = pymysql.connect(host='localhost', database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)
    db.autocommit(True)
    # prepare a cursor object using cursor() method
    cursor = db.cursor()

    query = (
        f"INSERT INTO trading.stock_account("
        f"symbol, instrument_type, contract_value, profit, account_type)"
        f"VALUES ('{symbol}', '{instrument_type}', '{contract_value}', '{profit}', '{account_type}')"
        f"ON DUPLICATE KEY UPDATE "
        f"instrument_type='{instrument_type}', contract_value='{contract_value}', "
        f"profit='{profit}';"
    )
    cursor.execute(query)
    db.close()

add_stock_value(
    symbol="AAPL",
    instrument_type=StockInstrumentType.STOCK,
    contract_value=1010,
    profit=100,
    account_type=StockAccountType.EUR

)
