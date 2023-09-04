import json
from datetime import date
from alphaspread import ValuationType

# load nasdaq json from data
DATE_TODAY = str(date.today())
PREFIX = "data/nasdaq_analysis_"
READ_FILENAME = PREFIX + DATE_TODAY + ".json"
WRITE_FILENAME = PREFIX + DATE_TODAY + "_filtered.json"

with open(READ_FILENAME, "r") as f:
    nasdaq_json = json.load(f)

# UNDERVALUED_THRESHOLD = 15
SOLVENCY_THRESHOLD = 50

# filter nasdaq json for undervalued stocks that are also solvent

filtered_nasdaq_json = [
    stock
    for stock in nasdaq_json
    if stock["valuation_type"] == ValuationType.UNDERVALUED
    # and stock["valuation_score"] > UNDERVALUED_THRESHOLD
    and stock["solvency_score"] > SOLVENCY_THRESHOLD
]

# sort by undervalued score


# print filtered nasdaq json

print(json.dumps(filtered_nasdaq_json, indent=4))

# dump to file

with open(WRITE_FILENAME, "w") as f:
    json_str = json.dumps(filtered_nasdaq_json, indent=4)
    f.write(json_str)
