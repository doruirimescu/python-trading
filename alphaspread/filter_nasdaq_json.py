import json
from datetime import date
from alphaspread import ValuationType

# load nasdaq json from data

with open("nasdaq_analysis_2021-08-09.json", "r") as f:
    nasdaq_json = json.load(f)

UNDERVALUED_THRESHOLD = 50
SOLVENCY_THRESHOLD = 50

# filter nasdaq json for undervalued stocks that are also solvent

filtered_nasdaq_json = [
    stock
    for stock in nasdaq_json
    if stock["valuation_type"] == ValuationType.UNDERVALUED
    and stock["valuation_score"] > UNDERVALUED_THRESHOLD
    and stock["solvency_score"] > SOLVENCY_THRESHOLD
]

# sort by undervalued score


# print filtered nasdaq json

print(json.dumps(filtered_nasdaq_json, indent=4))

# dump to file

with open("filtered_nasdaq_analysis_2021-08-09.json", "w") as f:
    json_str = json.dumps(filtered_nasdaq_json, indent=4)
    f.write(json_str)
