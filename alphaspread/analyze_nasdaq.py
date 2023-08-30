import json
from datetime import date
from typing import List
import requests
from alphaspread import analyze_url

DATE_TODAY = date.today()
ANALYSIS_FILENAME = f"data/nasdaq_analysis_{DATE_TODAY}.json"

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
    for symbol in nasdaq_symbols:
        url = f"https://www.alphaspread.com/security/nasdaq/{symbol}/summary"
        try:
            analysis = analyze_url(url, symbol)
            undervalued_symbols.append(analysis)
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")

    with open(ANALYSIS_FILENAME, "w") as f:
        json_str = json.dumps(
            [analysis.dict() for analysis in undervalued_symbols], indent=4
        )
        f.write(json_str)
