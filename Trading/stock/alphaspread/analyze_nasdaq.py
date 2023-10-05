import json
from Trading.symbols.wrapper import get_nasdaq_symbols
from alphaspread import analyze_url
from constants import NASDAQ_ANALYSIS_FILENAME
from time import sleep
import os


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
