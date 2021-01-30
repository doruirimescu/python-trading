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

#symbols maps a symbol to a tuple (address, pairID) - find the pairID by inspecting the network traffic response
symbols = {
#Forex
'USDJPY'    : ('https://www.investing.com/currencies/usd-jpy', 3),
'AUDCAD'    : ('https://www.investing.com/currencies/aud-cad', 47),
'AUDCHF'    : ('https://www.investing.com/currencies/aud-chf', 48),
'AUDJPY'    : ('https://www.investing.com/currencies/aud-jpy', 49),
'AUDNZD'    : ('https://www.investing.com/currencies/aud-nzd', 50),
'AUDUSD'    : ('https://www.investing.com/currencies/aud-usd', 5),
'CADCHF'    : ('https://www.investing.com/currencies/cad-chf', 14),
'CADJPY'    : ('https://www.investing.com/currencies/cad-jpy', 51),
'CHFHUF'    : ('https://www.investing.com/currencies/chf-huf', 90),
'CHFJPY'    : ('https://www.investing.com/currencies/chf-jpy', 51),
'CHFPLN'    : ('https://www.investing.com/currencies/chf-pln', 86),
'EURAUD'    : ('https://www.investing.com/currencies/eur-aud', 15),
'EURCAD'    : ('https://www.investing.com/currencies/eur-cad', 16),
'EURCHF'    : ('https://www.investing.com/currencies/eur-chf', 10),
'EURCNH'    : ('https://www.investing.com/currencies/eur-cnh', 1623),
'EURCZK'    : ('https://www.investing.com/currencies/eur-czk', 156),
'EURGBP'    : ('https://www.investing.com/currencies/eur-gbp', 6),
'EURHUF'    : ('https://www.investing.com/currencies/eur-huf', 117),
'EURJPY'    : ('https://www.investing.com/currencies/eur-jpy', 9),
'EURMXN'    : ('https://www.investing.com/currencies/eur-mxn', 101),
'EURNOK'    : ('https://www.investing.com/currencies/eur-nok', 37),
'EURNZD'    : ('https://www.investing.com/currencies/eur-nzd', 52),
'EURPLN'    : ('https://www.investing.com/currencies/eur-pln', 46),
'EURRON'    : ('https://www.investing.com/currencies/eur-ron', 1689),
'EURRUB'    : ('https://www.investing.com/currencies/eur-rub', 1691),
'EURSEK'    : ('https://www.investing.com/currencies/eur-sek', 61),
'EURTRY'    : ('https://www.investing.com/currencies/eur-try', 66),
'EURUSD'    : ('https://www.investing.com/currencies/eur-usd', 1),

#Indices


#Crypto
'BTCUSD'    : ('https://www.investing.com/crypto/bitcoin/btc-usd', 945629),
'ETHUSD'    : ('https://www.investing.com/crypto/ethereum/eth-usd', 997650),
'ETHBTC'    : ('https://www.investing.com/crypto/ethereum/eth-btc', 1010776),
'ADABTC'    : ('https://www.investing.com/crypto/cardano/ada-btc', 1055844),
'BCHBTC'    : ('https://www.investing.com/crypto/bitcoin-cash/bch-btc', 1031042),
'BCHUSD'    : ('https://www.investing.com/crypto/bitcoin-cash/bch-usd', 1058255),
'DASH'      : ('https://www.investing.com/crypto/dash/dash-usd', 1010785),
'DSHBTC'    : ('https://www.investing.com/crypto/dash/dash-btc',1010783),
'EOS'       : ('https://www.investing.com/crypto/eos/eos-usd', 1119415),
'EOSBTC'    : ('https://www.investing.com/crypto/eos/eos-btc', 1129125),
'EOSETH'    : ('https://www.investing.com/crypto/eos/eos-eth', 1058146),

#Stocks
'GME'       : ('https://www.investing.com/equities/gamestop-corp', 13845),

#Commodities
'NATGAS'    :  ('https://www.investing.com/commodities/natural-gas-technical',8862),
'SILVER'    : ('https://www.investing.com/commodities/silver', 8836),
'GOLD'      : ('https://www.investing.com/commodities/gold', 8830),
'NATGAS'    :  ('https://www.investing.com/commodities/gold',8862)
}


def getAvailableSymbols():
    response = [i for i,j in symbols.items()]
    return response

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
    symbol = symbol.upper()
    headers = { 'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': symbols[symbol][0],
            'X-Requested-With': 'XMLHttpRequest'}

    periods = {'1m' : 60, '5m':300, '15m' : 900 ,'30m' : 1800, '1h': 3600, '5h': 18000, 'D': 86400, 'W': 'week', 'M':'month'}

    body = {'pairID' : symbols[symbol][1], 'period': '', 'viewType' : 'normal'}

    with requests.Session() as s:
        body['period'] = periods[period]
        r = s.post('https://www.investing.com/instruments/Service/GetTechincalData', data = body, headers = headers)
        soup = bs(r.content, 'lxml')
        response = list()

        for i in soup.select('#techStudiesInnerWrap .summary'):
            response_text = i.select('span')[0].text.upper()
            print(response_text)
            response.append(string_to_enum[response_text.upper()])
    return response

print(getInvestingResponse('EURTRY', '30m'))
#print(getAvailableSymbols())
