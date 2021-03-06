import requests
from bs4 import BeautifulSoup as bs
from enum import Enum
from datetime import datetime
# Defines a response from investing.com
class InvestingAnalysisResponse(Enum):
    """Enumeration class for investing.com analysis response"""

    STRONG_SELL = 1
    SELL = 2
    NEUTRAL = 3
    BUY = 4
    STRONG_BUY = 5


class Investing:
    def __init__(self):
        self.string_to_enum = {
            "STRONG SELL": InvestingAnalysisResponse.STRONG_SELL,
            "SELL": InvestingAnalysisResponse.SELL,
            "NEUTRAL": InvestingAnalysisResponse.NEUTRAL,
            "BUY": InvestingAnalysisResponse.BUY,
            "STRONG BUY": InvestingAnalysisResponse.STRONG_BUY,
        }

        # symbols maps a symbol to a tuple (address, pairID) - find the pairID by inspecting the network traffic response
        self.symbols = {
            # Forex
            "USDJPY": ("https://www.investing.com/currencies/usd-jpy", 3),
            "AUDCAD": ("https://www.investing.com/currencies/aud-cad", 47),
            "AUDCHF": ("https://www.investing.com/currencies/aud-chf", 48),
            "AUDJPY": ("https://www.investing.com/currencies/aud-jpy", 49),
            "AUDNZD": ("https://www.investing.com/currencies/aud-nzd", 50),
            "AUDUSD": ("https://www.investing.com/currencies/aud-usd", 5),
            "CADCHF": ("https://www.investing.com/currencies/cad-chf", 14),
            "CADJPY": ("https://www.investing.com/currencies/cad-jpy", 51),
            "CHFHUF": ("https://www.investing.com/currencies/chf-huf", 90),
            "CHFJPY": ("https://www.investing.com/currencies/chf-jpy", 51),
            "CHFPLN": ("https://www.investing.com/currencies/chf-pln", 86),
            "EURAUD": ("https://www.investing.com/currencies/eur-aud", 15),
            "EURCAD": ("https://www.investing.com/currencies/eur-cad", 16),
            "EURCHF": ("https://www.investing.com/currencies/eur-chf", 10),
            "EURCNH": ("https://www.investing.com/currencies/eur-cnh", 1623),
            "EURCZK": ("https://www.investing.com/currencies/eur-czk", 156),
            "EURGBP": ("https://www.investing.com/currencies/eur-gbp", 6),
            "EURHUF": ("https://www.investing.com/currencies/eur-huf", 117),
            "EURJPY": ("https://www.investing.com/currencies/eur-jpy", 9),
            "EURMXN": ("https://www.investing.com/currencies/eur-mxn", 101),
            "EURNOK": ("https://www.investing.com/currencies/eur-nok", 37),
            "EURNZD": ("https://www.investing.com/currencies/eur-nzd", 52),
            "EURPLN": ("https://www.investing.com/currencies/eur-pln", 46),
            "EURRON": ("https://www.investing.com/currencies/eur-ron", 1689),
            "EURRUB": ("https://www.investing.com/currencies/eur-rub", 1691),
            "EURSEK": ("https://www.investing.com/currencies/eur-sek", 61),
            "EURTRY": ("https://www.investing.com/currencies/eur-try", 66),
            "EURUSD": ("https://www.investing.com/currencies/eur-usd", 1),
            # Indices
            "DE30": ("https://www.investing.com/indices/germany-30", 172),
            "EU50": ("https://www.investing.com/indices/eu-stocks-50-futures", 8867),
            "UK100": ("https://www.investing.com/indices/uk-100", 27),
            "US30": ("https://www.investing.com/indices/us-30", 169),
            "US500": ("https://www.investing.com/indices/us-spx-500", 166),
            # Crypto
            "BTCUSD": ("https://www.investing.com/crypto/bitcoin/btc-usd", 945629),
            "ETHUSD": ("https://www.investing.com/crypto/ethereum/eth-usd", 997650),
            "ETHBTC": ("https://www.investing.com/crypto/ethereum/eth-btc", 1010776),
            "ADABTC": ("https://www.investing.com/crypto/cardano/ada-btc", 1055844),
            "BCHBTC": (
                "https://www.investing.com/crypto/bitcoin-cash/bch-btc",
                1031042,
            ),
            "BCHUSD": (
                "https://www.investing.com/crypto/bitcoin-cash/bch-usd",
                1058255,
            ),
            "DASH": ("https://www.investing.com/crypto/dash/dash-usd", 1010785),
            "DSHBTC": ("https://www.investing.com/crypto/dash/dash-btc", 1010783),
            "EOS": ("https://www.investing.com/crypto/eos/eos-usd", 1119415),
            "EOSBTC": ("https://www.investing.com/crypto/eos/eos-btc", 1129125),
            "EOSETH": ("https://www.investing.com/crypto/eos/eos-eth", 1058146),
            # Stocks
            "GME": ("https://www.investing.com/equities/gamestop-corp", 13845),
            # Commodities
            "NATGAS": (
                "https://www.investing.com/commodities/natural-gas-technical",
                8862,
            ),
            "SILVER": ("https://www.investing.com/commodities/silver", 8836),
            "GOLD": ("https://www.investing.com/commodities/gold", 8830),
            "NATGAS": ("https://www.investing.com/commodities/gold", 8862),
        }

    def getAvailableSymbols(self):
        response = [i for i, j in self.symbols.items()]
        return response

    def getTechnicalAnalysis(self, symbol, period):
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
                response_text = i.select("span")[0].text.upper()
                print(response_text)
                response.append(self.string_to_enum[response_text.upper()])
        return response

    def sanitizeTimeframe(self, timeframe):
        if timeframe == "1":
            return "1m"
        elif timeframe == "5":
            return "5m"
        elif timeframe == "15":
            return "15m"
        elif timeframe == "30":
            return "30m"
        return timeframe

    def getTimeFormatter(self, timeframe):
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
            return "%b %Y"

    def getCandlestickAnalysis(self, symbol, period=None):
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
            response = list()

            row_id = 0
            table = soup.find("tr", id="row" + str(row_id))
            while table is not None:
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
                        timeframe = self.sanitizeTimeframe(timeframe)
                    elif counter == 7:
                        reliability = child["title"]
                    elif counter == 9:
                        candles_ago = child.contents[0]
                    elif counter == 11:
                        date = child.contents[0]
                    counter += 1

                if (period is None) or (timeframe == period):
                    print("Pattern: \t" + pattern)
                    print("Timeframe: \t" + timeframe)
                    print("Reliability: \t" + reliability)
                    print("Candles ago: \t" + candles_ago)
                    print("Date: \t" + date)
                    print("------------------------------")

                row_id += 1
                table = soup.find("tr", id="row" + str(row_id))


i = Investing()

print(i.getTechnicalAnalysis("BTCUSD", "30m"))
print(i.getCandlestickAnalysis("BTCUSD", "30m"))
