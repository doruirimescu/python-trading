import requests
from bs4 import BeautifulSoup as bs
from Trading.live.investing_api.symbols_url import SYMBOLS_URL
from Trading.instrument.timeframes import TIMEFRAMES
from Trading.algo.technical_analyzer.technical_analysis import TechnicalAnalysis
from Trading.instrument.instrument import Instrument
__all__ = ['InvestingTechnicalAnalyzer']


class InvestingTechnicalAnalyzer:
    """Investing.com technical analyzer which generates TechnicalAnalysis responses
    """

    def __init__(self):

        # symbols maps a symbol to a tuple (address, pairID) - find the pairID by inspecting the network traffic response
        self.symbols = SYMBOLS_URL

    def analyse(self, instrument: Instrument) -> TechnicalAnalysis:
        soup = self.__get_soup(instrument.get_symbol_investing(), instrument.timeframe)
        for i in soup.select("#techStudiesInnerWrap .summary"):
            response_text = i.select("span")[0].text
            return(TechnicalAnalysis(response_text))

    def __get_soup(self, symbol, period):
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
