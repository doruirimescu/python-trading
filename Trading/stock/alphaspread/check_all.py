import json
from Trading.stock.alphaspread.alphaspread import analyze_url, Analysis, ValuationType

# read json file to dict
with open('/home/doru/personal/trading/Trading/symbols/alphaspread/urls.json', 'r') as f:
    data = json.load(f)

found_trades = {}
for key, value in data.items():
    if value is None:
        continue
    try:
        analysis = analyze_url(value, key)
    except:
        continue
    solvency = analysis.solvency_score
    valuation_type = analysis.valuation_type
    valuation = analysis.valuation_score
    if analysis.valuation_type == "OVERVALUED":
        continue
    if solvency is None or solvency < 70:
        continue
    if valuation_type == ValuationType.OVERVALUED:
        continue
    if valuation < 30:
        continue
    found_trades[key] = value
    print(f'{key}: {value} {solvency} {valuation_type} {valuation}')
print(f'found_trades: {len(found_trades)}')
with open('/home/doru/personal/trading/Trading/generated/alphaspread_trades.json', 'w') as f:
    json.dump(found_trades, f, indent=4)
