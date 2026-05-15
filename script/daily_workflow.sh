#!/usr/bin/env bash
set -e

python3 Trading/stock/analyze_nasdaq.py --nasdaq
python3 Trading/stock/analyze_nasdaq.py --sp500

pip install -q "kaleido==0.2.1"
python3 Trading/stock/visualize.py --nasdaq --save
python3 Trading/stock/visualize.py --sp500 --save

TODAY=$(date +%Y-%m-%d)
cp "Trading/generated/nasdaq/nasdaq_analysis_${TODAY}.html" "docs/nasdaq_today.html"
cp "Trading/generated/sp500/sp500_analysis_${TODAY}.html" "docs/sp500_today.html"

cat > docs/index.html <<EOF
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Daily Stock Analysis</title>
<style>body{font-family:sans-serif;max-width:600px;margin:60px auto;line-height:1.6}
a{display:block;margin:16px 0;font-size:1.2em}</style></head>
<body>
<h1>Daily Stock Analysis — ${TODAY}</h1>
<a href="nasdaq_today.html">NASDAQ 100 Valuation</a>
<a href="sp500_today.html">S&amp;P 500 Valuation</a>
</body></html>
EOF
