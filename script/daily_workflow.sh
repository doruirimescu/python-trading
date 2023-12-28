#!/usr/bin/env bash

# Nasdaq analysis
python3 Trading/stock/analyze_nasdaq.py --nasdaq
python3 Trading/stock/visualize.py --nasdaq --save
