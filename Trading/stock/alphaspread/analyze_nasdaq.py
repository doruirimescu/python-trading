import json
from typing import List
import requests
from alphaspread import analyze_url
from constants import NASDAQ_ANALYSIS_FILENAME
from time import sleep
import os

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


if __name__ == "__main__":
    nasdaq_symbols = get_nasdaq_symbols()
    undervalued_symbols = []

    if os.path.exists(NASDAQ_ANALYSIS_FILENAME):
        with open(NASDAQ_ANALYSIS_FILENAME, "r") as f:
            # load json
            json_str = f.read()
            data = json.loads(json_str)
    else:
        data = []

    for symbol in nasdaq_symbols:
        # Check if symbol is already in json
        should_continue = False
        for d in data:
            if symbol in d["symbol"]:
                print(f"Skipping {symbol}")
                should_continue = True
                break
        if should_continue:
            continue

        url = f"https://www.alphaspread.com/security/nasdaq/{symbol}/summary"
        try:
            analysis = analyze_url(url, symbol)
            undervalued_symbols.append(analysis)

            # add analysis to json
            data.append(analysis.dict())

        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")

        sleep(3.0)

    with open(NASDAQ_ANALYSIS_FILENAME, "w") as f:
        json_str = json.dumps(
            data, indent=4
        )
        f.write(json_str)
