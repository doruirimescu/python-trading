#!/usr/bin/env bash
set -e

python3 Trading/stock/analyze_nasdaq.py --nasdaq

echo y | plotly_get_chrome
python3 Trading/stock/visualize.py --nasdaq --save
