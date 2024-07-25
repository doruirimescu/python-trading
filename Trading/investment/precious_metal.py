
from Trading.model.investment import PreciousMetalInvestments, PreciousMetalInvestment
from stateful_data_processor.file_rw import JsonFileRW
from pathlib import Path
import os

import argparse

if __name__ == "__main__":
    CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))

    # create argument parser
    parser = argparse.ArgumentParser(description="Investment tracker for precious metals")
    parser.add_argument("--path", type=str, help="Path to the json investment file", default="silver_new.json")
    parser.add_argument("--current_market_price_g", type=float, help="Current market price in EUR per gram")
    args = parser.parse_args()
    path = args.path
    current_market_price_g = args.current_market_price_g

    file_reader = JsonFileRW(CURRENT_FILE_PATH.joinpath(path))
    data = file_reader.read()
    investments = PreciousMetalInvestments([PreciousMetalInvestment(**entry) for entry in data])

    print(investments.summarize(current_market_price_g))
