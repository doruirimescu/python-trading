from exception_with_retry import exception_with_retry
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from Trading.live.client.client import XTBTradingClient
from Trading.symbols.constants import XTB_ALL_SYMBOLS_DICT
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.stock.alphaspread.url import get_alphaspread_symbol_url
from Trading.stock.alphaspread.alphaspread import (
    analyze_url,
    valuation_type_order,
    ValuationType,
)
from dotenv import load_dotenv
from datetime import date
import json
import os
import logging

# open all symbols file
# Monitor stock allocations

# get current file path
CURRENT_FILE_PATH = os.path.dirname(os.path.realpath(__file__))


TMP_FILENAME = CURRENT_FILE_PATH + "/" + (f"tmp_{date.today()}.json")


def get_data_from_broker(client):
    stock_contract_value = dict()
    stock_profits = dict()

    trades = client.get_open_trades()
    for trade in trades:
        if trade["closed"] or not trade["profit"]:
            continue

        symbol = trade["symbol"]
        nominal_value = trade["nominalValue"]
        print(f"Retrieving data for symbol {symbol}")

        # Filter out other instruments
        s = XTB_ALL_SYMBOLS_DICT[symbol]
        cat = s["categoryName"]
        if cat not in ["STC"]:
            continue

        # Add up contract value and profit
        if not stock_contract_value.get(symbol):
            stock_contract_value[symbol] = nominal_value
            stock_profits[symbol] = trade["profit"]
        else:
            stock_contract_value[symbol] += nominal_value
            stock_profits[symbol] += trade["profit"]

        s = client.get_symbol(symbol)
        cat = s["categoryName"]
    return stock_contract_value, stock_profits


@exception_with_retry(n_retry=10, sleep_time_s=5.0)
def monitor_once(client, should_plot=True):
    data_loaded_from_file = False
    if not os.path.isfile(TMP_FILENAME):
        stock_contract_value, stock_profits = get_data_from_broker(client)
    else:
        # load data from file
        with open(TMP_FILENAME, "r") as f:
            file_data = json.load(f)
            stock_contract_value = file_data["stock_contract_value"]
            stock_profits = file_data["stock_profits"]
            stock_valuation = file_data["stock_valuation"]
            data_loaded_from_file = True

    total_portfolio_contract_value = sum(stock_contract_value.values())
    total_portfolio_profit = sum(stock_profits.values())

    stock_contract_value_percentage = dict()
    stock_profits_percentage = dict()
    for symbol in stock_contract_value.keys():
        stock_contract_value_percentage[symbol] = (
            stock_contract_value[symbol] / total_portfolio_contract_value
        )
        stock_profits_percentage[symbol] = (
            stock_profits[symbol] / total_portfolio_profit
        )

    # Data for pie chart
    labels = list(stock_contract_value_percentage.keys())
    labels = [XTB_ALL_SYMBOLS_DICT[l]["description"].strip() for l in labels]
    sizes = list(stock_contract_value_percentage.values())

    if not data_loaded_from_file:
        stock_valuation = dict()
        for stock_name in labels:
            try:
                symbol, url = get_alphaspread_symbol_url(stock_name)
                analysis = analyze_url(url, symbol)
                stock_valuation[stock_name] = (
                    analysis.valuation_type,
                    analysis.valuation_score,
                    analysis.solvency_score,
                )
            except Exception as e:
                MAIN_LOGGER.error(f"Error analyzing {stock_name}: {e}")

    # Sort the dictionary using the new sort order
    sorted_stock_valuation_new = sorted(
        stock_valuation.items(),
        key=lambda item: (
            valuation_type_order[item[1][0]],
            -item[1][1] if item[1][0] == ValuationType.OVERVALUED else item[1][1],
        ),
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

    with open(TMP_FILENAME, "w") as f:
        json.dump(
            {
                "stock_contract_value": stock_contract_value,
                "stock_profits": stock_profits,
                "stock_valuation": stock_valuation,
            },
            f,
            indent=4,
            sort_keys=True,
            default=str,
        )

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
    client = XTBTradingClient(USERNAME, PASSWORD, MODE, False)

    monitor_once(client, should_plot=True)
