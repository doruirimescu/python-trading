#!/usr/bin/env bash
set -e

python3 Trading/stock/analyze_nasdaq.py --nasdaq

pip install -q "kaleido==0.2.1"
python3 Trading/stock/visualize.py --nasdaq --save
