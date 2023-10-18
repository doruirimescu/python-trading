from fastapi import APIRouter
import Trading.stock.constants as constants
from Trading.stock.analyze_nasdaq import analyze
from Trading.stock.visualize import prepare_data
import os
import Trading.live.monitoring.monitor_stocks as monitor_stocks
router = APIRouter()


@router.get("/nasdaq")
def analyse():
    # check if file exists
    if not os.path.isfile(constants.NASDAQ_ANALYSIS_FILENAME):
        analyze(constants.NASDAQ_ANALYSIS_FILENAME)

    stock_names, scores, solvencies, valuation_types = prepare_data(
        constants.NASDAQ_ANALYSIS_FILENAME
    )
    colors = ["red" if item == "Overvalued" else "green" for item in valuation_types]

    return {
        "name": stock_names,
        "score": scores,
        "color": colors,
        "solvency": solvencies,
    }

@router.get("/portfolio/usd/pie")
def analyse_usd_portfolio():
    return monitor_stocks.monitor_usd()["pie"]

@router.get("/portfolio/usd/valuation")
def analyse_usd_portfolio():
    return monitor_stocks.monitor_usd()["valuation"]
