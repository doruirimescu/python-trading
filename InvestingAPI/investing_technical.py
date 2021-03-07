import requests
from bs4 import BeautifulSoup as bs
from enum import Enum
from datetime import datetime
import symbols_url

# Defines a response from investing.com
class InvestingAnalysisResponse(Enum):
    """Enumeration class for investing.com analysis response"""

    STRONG_SELL = "Strong Sell"
    SELL = "Sell"
    NEUTRAL = "Neutral"
    BUY = "Buy"
    STRONG_BUY = "Strong Buy"
#TODO call class InvestingTechnicalAnalysis
#TODO get confidence number for tech analysis
class Investing:
    def __init__(self):

        # symbols maps a symbol to a tuple (address, pairID) - find the pairID by inspecting the network traffic response
        self.symbols = symbols_url.SYMBOLS_URL

    def getAvailableSymbols(self):
        response = [i for i, j in self.symbols.items()]
        return response

    def getAnalysis(self, symbol, period):
        symbol = symbol.upper()
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.symbols[symbol][0],
            "X-Requested-With": "XMLHttpRequest",
        }

        periods = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "5h": 18000,
            "D": 86400,
            "W": "week",
            "M": "month",
        }

        body = {"pairID": self.symbols[symbol][1], "period": "", "viewType": "normal"}

        with requests.Session() as s:
            body["period"] = periods[period]
            r = s.post(
                "https://www.investing.com/instruments/Service/GetTechincalData",
                data=body,
                headers=headers,
            )
            soup = bs(r.content, "lxml")
            response = list()

            for i in soup.select("#techStudiesInnerWrap .summary"):
                response_text = i.select("span")[0].text
                print(response_text)
                response.append(InvestingAnalysisResponse(response_text))
        return response


i = Investing()
print(i.getAnalysis("BTCUSD", "30m"))
