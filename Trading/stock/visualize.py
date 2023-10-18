import json
import plotly.express as px
from plotly.subplots import make_subplots

import plotly.graph_objects as go
from Trading.stock.constants import (FILTERED_NASDAQ_ANALYSIS_FILENAME,
                                     EUROPE_ANALYSIS_FILENAME,
                                     NASDAQ_ANALYSIS_FILENAME,
                                     HELSINKI_NASDAQ_ANALYSIS_FILENAME,)
from Trading.stock.alphaspread.alphaspread import valuation_type_order, ValuationType
import argparse



def plot_bars(stock_names, scores, solvencies, valuation_types):
    fig = make_subplots(
                rows=1, cols=1,
                subplot_titles=("Top Stocks Valuation"),
                specs=[[{"type": "xy"}]]
        )

    texts = [f"Valuation: {score}, Solvency: {solvency}" for score, solvency in zip(scores, solvencies)]

    colors = ['red' if item == 'Overvalued' else 'green' for item in valuation_types]

    fig.add_trace(go.Bar(x=stock_names, y=scores, text=texts, textposition='auto', marker_color=colors), row=1, col=1)

    # Update layout
    fig.update_layout(title_text="Stock Analysis")
    fig.show()

def prepare_data(filename):
    # open data file
    with open(filename, "r") as f:
        data = json.load(f)

    stock_valuation = dict()
    for stk in data:
        symbol = stk["symbol"]
        valuation_type = stk["valuation_type"]
        valuation_score = stk["valuation_score"]
        solvency_score = stk["solvency_score"]
        stock_valuation[symbol] = (valuation_type, valuation_score, solvency_score)


    sorted_stock_valuation_new = sorted(
                stock_valuation.items(),
                key=lambda item: (item[1][2] if item[1][2] else 0, item[1][1]),
            )


    # Add bar chart
    stock_names = [item[0] for item in sorted_stock_valuation_new]
    scores = [item[1][1] for item in sorted_stock_valuation_new]
    solvencies = [item[1][2] for item in sorted_stock_valuation_new]
    valuation_types = [item[1][0] for item in sorted_stock_valuation_new]

    return stock_names, scores, solvencies, valuation_types

if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--helsinki", action="store_true")
    arg.add_argument("--nasdaq", action="store_true")
    arg.add_argument("--filtered", action="store_true")
    args = arg.parse_args()

    if args.helsinki:
        filename = HELSINKI_NASDAQ_ANALYSIS_FILENAME
    elif args.nasdaq:
        if args.filtered:
            filename = FILTERED_NASDAQ_ANALYSIS_FILENAME
        else:
            filename = NASDAQ_ANALYSIS_FILENAME
    stock_names, scores, solvencies, valuation_types = prepare_data(filename)
    plot_bars(stock_names, scores, solvencies, valuation_types)
