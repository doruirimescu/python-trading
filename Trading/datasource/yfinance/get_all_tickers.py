from Trading.datasource.yfinance.constants import ALL_EXCHANGES
from Trading.config.config import YFINANCE_DOWNLOADS_PATH
from Trading.utils.time import get_datetime_now_cet
from yfinance import EquityQuery
import yfinance as yf
import json
from stateful_data_processor.processor import StatefulDataProcessor
from stateful_data_processor.file_rw import JsonFileRW

from Trading.utils.custom_logging import get_logger

LOGGER = get_logger(__file__)

class YFinanceTickersScraper(StatefulDataProcessor):
    def __init__(self, json_file_writer: JsonFileRW):
        # Initialize the base class
        super().__init__(json_file_writer, logger=LOGGER)
    def process_item(self, item: str, iteration_index):
        query = EquityQuery('is-in', ['exchange', item])
        offset = 0
        while True:
            res = yf.screen(query, offset=offset, size=250, count=250)
            offset += 250
            start = int(res['start'])
            total = int(res['total'])
            quotes = res["quotes"]

            if item not in self.data:
                self.data[item] = {}
            for quote in quotes:
                q = {"currency" : quote.get("currency"),
                    "exchange" : quote.get("exchange"),
                    "exchangeTimezoneName" : quote.get("exchangeTimezoneName"),
                    "exchangeTimezoneShortName" : quote.get("exchangeTimezoneShortName"),
                    "financialCurrency" : quote.get("financialCurrency"),
                    "fullExchangeName" : quote.get("fullExchangeName"),
                    "language" : quote.get("language"),
                    "longName" : quote.get("longName"),
                    "market" : quote.get("market"),
                    "messageBoardId" : quote.get("messageBoardId"),
                    "quoteType" : quote.get("quoteType"),
                    "region" : quote.get("region"),
                    "shortName" : quote.get("shortName"),
                    "symbol" : quote.get("symbol"),
                    "typeDisp" : quote.get("typeDisp"),
                }
                self.data[item][q['symbol']] = q
            if start + offset >= total:
                return

if __name__ == "__main__":
    LOGGER.info("Starting yFinance tickers analysis")
    now_date= get_datetime_now_cet().date()
    filename = (
                YFINANCE_DOWNLOADS_PATH
                / f"{str(now_date)}-all-scrapers.json"
            )
    LOGGER.info(f"Writing results to {filename}")
    json_file_rw = JsonFileRW(filename)
    scraper = YFinanceTickersScraper(json_file_rw)
    ALL_EXCHANGES = list(set(ALL_EXCHANGES))  # Remove duplicates if any
    scraper.run(items=ALL_EXCHANGES)

    data = json_file_rw.read()
    combined_data = {}
    for exchange, tickers in data.items():
        combined_data.update(tickers)
    print(f"Total unique tickers scraped: {len(combined_data)}")
