#!/usr/bin/env bash
set -e

python3 Trading/macro/run_monthly_analysis.py
python3 Trading/stock/fetch_sp500_weights.py
