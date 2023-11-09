import json
from Trading.symbols.wrapper import get_nasdaq_symbols, get_nasdaq_helsinki_symbols, get_alphaspread_nasdaq_url
from Trading.stock.alphaspread.alphaspread import analyze_url
from Trading.stock.alphaspread.url import get_alphaspread_url
from Trading.stock.constants import NASDAQ_ANALYSIS_FILENAME, HELSINKI_NASDAQ_ANALYSIS_FILENAME
from time import sleep
import sys
import os

import argparse

SLEEP_TIME = 2.0


def analyze(filename):
    undervalued_symbols = []
    print("Getting symbols")
    nasdaq_symbols = get_nasdaq_symbols()
    print("Done getting symbols")

    if os.path.exists(filename):
        with open(filename, "r") as f:
            # load json
            json_str = f.read()
            data = json.loads(json_str)
    else:
        data = []

    print(nasdaq_symbols)
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

        url = get_alphaspread_nasdaq_url(symbol)
        try:
            analysis = analyze_url(url, symbol)
            undervalued_symbols.append(analysis)

            # add analysis to json
            data.append(analysis.dict())

        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
        sleep(SLEEP_TIME)

    with open(filename, "w") as f:
        json_str = json.dumps(
            data, indent=4
        )
        f.write(json_str)

if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--helsinki", action="store_true")
    arg.add_argument("--nasdaq", action="store_true")
    args = arg.parse_args()

    if args.helsinki:
        nasdaq_symbols = get_nasdaq_helsinki_symbols()
        filename = HELSINKI_NASDAQ_ANALYSIS_FILENAME
        url_getter = get_alphaspread_url
    elif args.nasdaq:
        nasdaq_symbols = get_nasdaq_symbols()
        filename = NASDAQ_ANALYSIS_FILENAME
        url_getter = get_alphaspread_nasdaq_url
    else:
        print("Please specify --helsinki or --nasdaq")
        sys.exit(1)

    if __name__ == "__main__":
        analyze(filename)
