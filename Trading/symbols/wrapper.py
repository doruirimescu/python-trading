import requests
from typing import List, Set
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT


def get_nasdaq_symbols() -> List:
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    }
    res = requests.get(
        "https://api.nasdaq.com/api/quote/list-type/nasdaq100", headers=headers
    )
    main_data = res.json()["data"]["data"]["rows"]
    symbols = []
    for i in range(len(main_data)):
        symbols.append(main_data[i]["symbol"])
    return symbols


def filter_xtb_symbols(countries: Set[str]={}, currencies: Set[str]={}) -> List:
    return [
        symbol
        for symbol in XTB_ALL_SYMBOLS_DICT
        if (not currencies or XTB_ALL_SYMBOLS_DICT[symbol]["currency"] in currencies) and
        (not countries or XTB_ALL_SYMBOLS_DICT[symbol]["groupName"] in countries)
    ]
