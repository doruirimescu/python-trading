from exception_with_retry import exception_with_retry
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from Trading.live.client.client import XTBTradingClient
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.stock.alphaspread.url import get_alphaspread_symbol_url
from Trading.stock.alphaspread.alphaspread import (
    analyze_url,
)
from dotenv import load_dotenv
from datetime import date
import json
import os
import logging
from time import sleep
from stateful_data_processor.file_rw import JsonFileRW
from Trading.live.monitoring.get_open_stock_trades import get_data_from_broker
from Trading.config.config import TMP_PATH

TMP_FILENAME = TMP_PATH / "monitor_stocks" /(f"{date.today()}.json")

USD_CVP_FILENAME = TMP_PATH / "monitor_stocks" / f"usd_cv_price_{date.today()}.json"
EUR_CVP_FILENAME = TMP_PATH / "monitor_stocks" / f"eur_cv_price_{date.today()}.json"

def get_alphaspread_valuations(stock_names):
    stock_valuation = dict()
    for stock_name in stock_names:
        if stock_name in stock_valuation:
            print("Skipping")
            continue
        try:
            symbol, url = get_alphaspread_symbol_url(stock_name)
            analysis = analyze_url(url, symbol)
            stock_valuation[stock_name] = (
                analysis.valuation_type,
                analysis.valuation_score,
                analysis.solvency_score,
            )
        except Exception as e:
            print(f"Error analyzing {stock_name}: {e}")

    return stock_valuation

@exception_with_retry(n_retry=10, sleep_time_s=5.0)
def monitor_once(client, should_plot=True):

    symbol_to_cv_profit = get_data_from_broker(client, USD_CVP_FILENAME)
    stock_valuation = get_alphaspread_valuations(symbol_to_cv_profit.keys())

    total_portfolio_contract_value = sum([cv for cv, _ in symbol_to_cv_profit.values()])
    total_portfolio_profit = sum([profit for _, profit in symbol_to_cv_profit.values()])

    stock_contract_value_percentage = dict()
    stock_profits_percentage = dict()
    for symbol in symbol_to_cv_profit.keys():
        cv = symbol_to_cv_profit[symbol][0]
        profit = symbol_to_cv_profit[symbol][1]

        stock_contract_value_percentage[symbol] = cv / total_portfolio_contract_value
        stock_profits_percentage[symbol] = profit / total_portfolio_profit

    # Data for pie chart
    labels = list(stock_contract_value_percentage.keys())
    labels = [XTB_ALL_SYMBOLS_DICT[l]["description"].strip() for l in labels]
    sizes = list(stock_contract_value_percentage.values())

    # Sort the dictionary using the new sort order
    sorted_stock_valuation_new = sorted(
        stock_valuation.items(),
        key=lambda item: (item[1][2] if item[1][2] is not None else 0,),
    )
    for stock_name, valuation in sorted_stock_valuation_new:
        print(f"{stock_name}: {valuation[0]} {valuation[1]}")

    solvencies = [item[1][2] for item in sorted_stock_valuation_new]
    stock_names = [item[0] for item in sorted_stock_valuation_new]
    scores = [item[1][1] for item in sorted_stock_valuation_new]
    texts = [
        f"Valuation: {score}, Solvency: {solvency}"
        for score, solvency in zip(scores, solvencies)
    ]
    colors = [
        "red" if item[1][0] == "Overvalued" else "green"
        for item in sorted_stock_valuation_new
    ]

    if should_plot:
        # Plotting
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=("Contract Value Percentage", "Top Stocks Valuation"),
            specs=[[{"type": "pie"}, {"type": "xy"}]],
        )
        # Create the pie chart
        fig.add_trace(go.Pie(labels=labels, values=sizes, hole=0.3), row=1, col=1)
        fig.add_trace(
            go.Bar(
                x=stock_names,
                y=scores,
                text=texts,
                textposition="auto",
                marker_color=colors,
            ),
            row=1,
            col=2,
        )

        # Update layout
        fig.update_layout(title_text="Stock Analysis")
        fig.show()

    pie = dict()
    pie["labels"] = labels
    pie["sizes"] = [s * 100 for s in sizes]
    pie["symbols"] = list(stock_contract_value_percentage.keys())

    colors = [
        "red" if item[1][0] == "Overvalued" else "green"
        for item in sorted_stock_valuation_new
    ]
    return {
        "pie": pie,
        "valuation": {
            "names": stock_names,
            "scores": scores,
            "colors": colors,
            "solvencies": solvencies,
        },
    }


def monitor_usd(should_plot=False):
    load_dotenv()
    username = os.getenv("USD_STOCKS")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(username, password, mode, False)
    return monitor_once(client, should_plot)


if __name__ == "__main__":
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger("Main logger")
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    load_dotenv()
    username = os.getenv("USD_STOCKS")
    password = os.getenv("XTB_PASSWORD")
    mode = os.getenv("XTB_MODE")
    client = XTBTradingClient(username, password, mode, False)

    monitor_once(client, should_plot=True)
