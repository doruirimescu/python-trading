import requests
from bs4 import BeautifulSoup as bs
from enum import Enum
from datetime import datetime
import symbols_url

class InvestingCandlestickAnalysisReliability(Enum):
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'
#TODO get confidence number for reliability
class InvestingCandleStickAnalysisResponse:
    def __init__(self, pattern, reliability, timeframe, candles_ago, date):
        self.pattern = pattern
        self.reliability = reliability
        self.timeframe = timeframe
        self.candles_ago = candles_ago
        self.date = date
        self.timestamp = datetime.timestamp(date)

    def print(self):
        print("Pattern: \t" + self.pattern)
        print("Timeframe: \t" + self.timeframe)
        print("Reliability: \t" + self.reliability.name)
        print("Candles ago: \t" + self.candles_ago)
        print(self.date)
        print("------------------------------")

class InvestingCandlestickAnalysis:
    def __init__(self):

        # symbols maps a symbol to a tuple (address, pairID) - find the pairID by inspecting the network traffic response
        self.symbols = symbols_url.SYMBOLS_URL

    def getAvailableSymbols(self):
        response = [i for i, j in self.symbols.items()]
        return response

    def __getTimeFormatter(self, timeframe):
        if timeframe =='1m':
            return "%b %d, %Y %I:%M%p"
        elif timeframe =='5m':
            return "%b %d, %Y %I:%M%p"
        elif timeframe =='15m':
            return "%b %d, %Y %I:%M%p"
        elif timeframe =='30m':
            return "%b %d, %Y %I:%M%p"
        elif timeframe =='1H':
            return "%b %d, %Y %I:%M%p"
        elif timeframe =='5H':
            return "%b %d, %Y %I:%M%p"
        elif timeframe =='1D':
            return "%b %d, %Y"
        elif timeframe =='1W':
            return "%b %d, %Y"
        elif timeframe =='1M':
            return "%b %y"

    def getAnalysis(self, symbol, period=None):

        soup = self.__getSoup(symbol)

        row_id = 0
        table = soup.find("tr", id="row" + str(row_id))
        while table is not None:
            response = self.__parseTable(table)

            if (response is not None) and (response.timeframe == period):
                response.print()

            row_id += 1
            table = soup.find("tr", id="row" + str(row_id))

    def __getSoup(self, symbol):
        symbol = symbol.upper()
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
        }
        url = self.symbols[symbol][0] + "-candlestick"

        with requests.Session() as s:
            r = s.post(url, headers=headers)
            soup = bs(r.content, "lxml")
            return soup
        return None

    def __parseTable(self, table):
        pattern = str()
        timeframe = str()
        reliability = str()
        candles_ago = str()
        date = str()

        counter = 0
        for child in table.contents:
            if counter == 3:
                pattern = child.contents[0]
            elif counter == 5:
                timeframe = child.contents[0]
                timeframe = self.__sanitizeTimeframe(timeframe)
            elif counter == 7:
                reliability = InvestingCandlestickAnalysisReliability(child["title"])
            elif counter == 9:
                candles_ago = child.contents[0]
            elif counter == 11:
                date = child.contents[0]
            counter += 1

        if date is '':
            print("EMPTY DATE")
            return None
        else:
            date = datetime.strptime(date, self.__getTimeFormatter(timeframe))

        return InvestingCandleStickAnalysisResponse(pattern, reliability, timeframe, candles_ago, date)

    def __sanitizeTimeframe(self, timeframe):
        if timeframe == "1":
            return "1m"
        elif timeframe == "5":
            return "5m"
        elif timeframe == "15":
            return "15m"
        elif timeframe == "30":
            return "30m"
        return timeframe

i = InvestingCandlestickAnalysis()
i.getAnalysis("BTCUSD", '30m')
