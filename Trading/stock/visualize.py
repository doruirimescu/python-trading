import json
import sys
from plotly.subplots import make_subplots
from typing import Optional, List
import plotly.graph_objects as go
from Trading.stock.constants import (
    FILTERED_NASDAQ_ANALYSIS_FILENAME,
    EUROPE_ANALYSIS_FILENAME,
    NASDAQ_ANALYSIS_FILENAME,
    HELSINKI_NASDAQ_ANALYSIS_FILENAME,
    SP500_ANALYSIS_FILENAME,
)
from Trading.config.config import NASDAQ_GENERATED_PATH, SP500_GENERATED_PATH
from Trading.symbols.wrapper import get_sp500_company_names
import argparse

def plot_bars(
    stock_names,
    scores: List[int],
    solvencies: List[int],
    valuation_types: List[str],
    company_names: Optional[List[str]] = None,
    should_save: bool = False,
    filename: Optional[str] = None,
    generated_path=NASDAQ_GENERATED_PATH,
):
    fig = make_subplots(
        rows=1,
        cols=1,
        subplot_titles=("Top Stocks Valuation"),
        specs=[[{"type": "xy"}]],
    )

    texts = [
        f"Valuation: {score}, Solvency: {solvency}"
        for score, solvency in zip(scores, solvencies)
    ]

    colors = ["red" if item == "Overvalued" else "green" for item in valuation_types]

    customdata = company_names if company_names else stock_names
    hovertemplate = (
        "<b>%{customdata}</b><br>"
        "Ticker: %{x}<br>"
        "Valuation score: %{y}<br>"
        "%{text}<extra></extra>"
    )

    fig.add_trace(
        go.Bar(
            x=stock_names,
            y=scores,
            text=texts,
            textposition="auto",
            marker_color=colors,
            customdata=customdata,
            hovertemplate=hovertemplate,
        ),
        row=1,
        col=1,
    )

    # Update layout
    fig.update_layout(title_text="Stock Analysis")
    fig.show()

    if should_save:
        # strip the path from filename
        filename = str(filename).split("/")[-1]
        # remove .json
        filename = filename.split(".")[0]

        # dump as png
        width = 1920 * 2  # Width of the image in pixels
        height = 1080 * 2  # Height of the image in pixels
        scale = 2  # Increase scale to improve quality
        generated_path.mkdir(parents=True, exist_ok=True)
        fig.write_image(generated_path / f"{filename}.png", width=width, height=height, scale=scale)

        # save html
        fig.write_html(generated_path / f"{filename}.html")


def prepare_data(filename):
    # open data file
    with open(filename, "r") as f:
        data = json.load(f)

    stock_valuation = dict()
    for key in data.keys():
        stk = data[key]
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
    arg.add_argument("--sp500", action="store_true")
    arg.add_argument("--filtered", action="store_true")
    arg.add_argument("--save", action="store_true")
    args = arg.parse_args()

    should_save = args.save
    out_path = NASDAQ_GENERATED_PATH

    company_names = None
    if args.helsinki:
        filename = HELSINKI_NASDAQ_ANALYSIS_FILENAME
    elif args.sp500:
        filename = SP500_ANALYSIS_FILENAME
        out_path = SP500_GENERATED_PATH
        names_map = get_sp500_company_names()
    elif args.nasdaq:
        filename = FILTERED_NASDAQ_ANALYSIS_FILENAME if args.filtered else NASDAQ_ANALYSIS_FILENAME
    else:
        print("Please specify --helsinki, --nasdaq, or --sp500")
        sys.exit(1)

    stock_names, scores, solvencies, valuation_types = prepare_data(filename)
    if args.sp500:
        company_names = [names_map.get(t, t) for t in stock_names]
    plot_bars(stock_names, scores, solvencies, valuation_types,
              company_names=company_names, should_save=should_save,
              filename=filename, generated_path=out_path)
