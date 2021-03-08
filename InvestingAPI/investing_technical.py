import requests
from bs4 import BeautifulSoup as bs
from enum import Enum
from datetime import datetime
import symbols_url
from timeframes import TIMEFRAMES as TIMEFRAMES

# Defines a response from investing.com
class TechnicalAnalysis(Enum):
    """Enumeration class for investing.com analysis response"""

    STRONG_SELL = "Strong Sell"
    SELL = "Sell"
    NEUTRAL = "Neutral"
    BUY = "Buy"
    STRONG_BUY = "Strong Buy"

class TechnicalAnalyzer:
    def __init__(self):

        # symbols maps a symbol to a tuple (address, pairID) - find the pairID by inspecting the network traffic response
        self.symbols = symbols_url.SYMBOLS_URL

    def getAvailableSymbols(self):
        response = [i for i, j in self.symbols.items()]
        return response

    def getAnalysis(self, symbol, period):
        soup = self.__getSoup(symbol, period)
        for i in soup.select("#techStudiesInnerWrap .summary"):
            response_text = i.select("span")[0].text
            return(TechnicalAnalysis(response_text))

    def __getSoup(self, symbol, period):
        symbol = symbol.upper()
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.symbols[symbol][0],
            "X-Requested-With": "XMLHttpRequest",
        }
        body = {"pairID": self.symbols[symbol][1], "period": "", "viewType": "normal"}

        with requests.Session() as s:
            periods = dict(zip(TIMEFRAMES, [60, 300, 900, 1800, 3600, 18000, 86400, 'week', 'month']))
            body["period"] = periods[period]
            r = s.post(
                "https://www.investing.com/instruments/Service/GetTechincalData",
                data=body,
                headers=headers,
            )
            soup = bs(r.content, "lxml")
            return soup
        return None

i = TechnicalAnalyzer()
print(i.getAnalysis("AUDUSD", "1h"))
