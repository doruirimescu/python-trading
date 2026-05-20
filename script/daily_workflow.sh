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

python3 Trading/stock/summarize.py
