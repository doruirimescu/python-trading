import requests
from bs4 import BeautifulSoup as bs
from enum import Enum

# Defines a response from investing.com
class InvestingAnalysisResponse(Enum):
    """Enumeration class for investing.com analysis response
    """
    STRONG_SELL = 1
    SELL = 2
    NEUTRAL = 3
    BUY = 4
    STRONG_BUY = 5

string_to_enum = {'STRONG SELL': InvestingAnalysisResponse.STRONG_SELL,
                'SELL' : InvestingAnalysisResponse.SELL,
                'NEUTRAL': InvestingAnalysisResponse.NEUTRAL,
                'BUY' : InvestingAnalysisResponse.BUY,
                'STRONG BUY' : InvestingAnalysisResponse.STRONG_BUY}




def getInvestingResponse(symbol, period):
    """Gets an investing.com response of the type InvestingAnalysisResponse
        Parameters
        ----------
        symbol : str
            The symbol to be analyzed
        period : str
            The period for the symbol to be analyzed
        Returns
        ----------
        response : InvestingAnalysisResponse
            The investing.com analysis
        """
    #symbols maps a symbol to a tuple (address, pairID) - find the pairID by inspecting the network traffic response
    symbols = { 'EURUSD'    : ('https://www.investing.com/currencies/eur-usd', 1),
                'USDJPY'    : ('https://www.investing.com/currencies/usd-jpy', 3),
                'BTCUSD'    : ('https://www.investing.com/crypto/bitcoin/btc-usd', 945629),
                'ETHUSD'    : ('https://www.investing.com/crypto/ethereum/eth-usd?cid=997650', 997650),
                'GME'       : ('https://www.investing.com/equities/gamestop-corp', 13845),
                'NATGAS'    :  ('https://www.investing.com/commodities/natural-gas-technical',8862)}

    headers = { 'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': symbols[symbol][0],
            'X-Requested-With': 'XMLHttpRequest'}

    periods = {'1m' : 60, '5m':300, '15m' : 900 ,'30m' : 1800, '1hr': 3600, '5hr': 18000, 'Daily': 86400, 'W': 'week', 'M':'month'}

    body = {'pairID' : symbols[symbol][1], 'period': '', 'viewType' : 'normal'}

    with requests.Session() as s:
        body['period'] = periods[period]
        r = s.post('https://www.investing.com/instruments/Service/GetTechincalData', data = body, headers = headers)
        soup = bs(r.content, 'lxml')
        response = list()

        for i in soup.select('#techStudiesInnerWrap .summary'):
            response_text = i.select('span')[0].text.upper()
            print(response_text)
            response.append(string_to_enum[response_text])
    return response
