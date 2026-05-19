import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import json as json_lib

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from loan.loan_vs_investment import perform_simulation
from loan.loan import LoanJsonParser
from stock.pvgo_calculator import calculate_pvgo
from stock.iv_15 import calculate_iv15_tragic_algebra
from stock.yfinance.dividend_sustainability import get_data, analyze_dividend_sustainability

app = FastAPI()

origins = [
    "https://doruirimescu.github.io",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:3000",
    # "null" covers pages opened directly from the filesystem (file://)
    "null",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -----------------------------------------

@app.get("/loan/simulate")
def loan_simulate(
    principal: int,
    interest_rate: float,
    fixed_monthly_installment: int,
    investment_return: float,
    monthly_salary: int,
    n_years: int,
):
    return perform_simulation(
        principal,
        interest_rate,
        fixed_monthly_installment,
        investment_return,
        monthly_salary,
        n_years,
        should_plot=False,
    )


def _serialize_payments(payments):
    return [
        {"date": str(p.date), "principal": p.principal, "interest": p.interest,
         "cost": p.cost, "interest_rate": p.interest_rate}
        for p in payments
    ]


@app.post("/loan/analyze")
async def loan_analyze(file: UploadFile = File(...)):
    content = await file.read()
    loan_data = json_lib.loads(content)

    # Build a parser that operates on the uploaded data without touching disk
    parser = LoanJsonParser.__new__(LoanJsonParser)
    parser.LOAN_DATA = loan_data

    principal_total = parser.principal_total(loan_data)
    principal_paid = parser.principal_paid(loan_data)
    principal_remaining = round(principal_total - principal_paid, 3)
    interest_paid = parser.interest_paid(loan_data)
    cost_paid = parser.cost_paid(loan_data)
    interest_rate = parser.get_effective_interest_rate(loan_data)
    upcoming_monthly_interest = round((principal_remaining * interest_rate / 100) / 12, 2)

    history = _serialize_payments(parser.loan_history(loan_data))
    cumulative = _serialize_payments(parser.cumulative_principal_paid(loan_data))

    avg_monthly_principal = (
        round(sum(p["principal"] for p in history) / len(history), 2) if history else 0
    )

    return {
        "principal_total": principal_total,
        "principal_paid": principal_paid,
        "principal_remaining": principal_remaining,
        "interest_paid": interest_paid,
        "cost_paid": cost_paid,
        "interest_and_cost_paid": round(interest_paid + cost_paid, 3),
        "interest_rate": interest_rate,
        "upcoming_monthly_interest": upcoming_monthly_interest,
        "avg_monthly_principal": avg_monthly_principal,
        "history": history,
        "cumulative_principal_paid": cumulative,
    }


@app.get("/iv15/calculate")
def iv15_calculate(
    ticker: str,
    growth_rate: float = 0.15,
    terminal_multiple: float = 15,
    manual_sbc: Optional[float] = None,
):
    # manual_sbc is accepted in dollars; frontend sends millions * 1e6
    result = calculate_iv15_tragic_algebra(ticker, growth_rate, terminal_multiple, manual_sbc)
    if isinstance(result, str):
        return {"error": result}
    return result


@app.get("/pvgo/calculate")
def pvgo_calculate(ticker: str, market_risk_premium: float = 0.05):
    result = calculate_pvgo(ticker, market_risk_premium)
    if isinstance(result, str):
        return {"error": result}
    return result


@app.get("/dividend/sustainability")
def dividend_sustainability(tickers: str, threshold: int = 65):
    ticker_list = [t.strip().upper() for t in tickers.replace("\n", ",").split(",") if t.strip()]
    results = []
    skipped = []

    for ticker in ticker_list:
        try:
            data, dividends = get_data(ticker)
            if data.get("dividendYield") is None:
                skipped.append({"ticker": ticker, "reason": "no dividend yield data"})
                continue
            is_sustainable, score, yield_val, _ = analyze_dividend_sustainability(
                data, dividends, threshold=threshold
            )
            name = data.get("longName") or data.get("shortName") or ticker
            results.append({
                "ticker": ticker,
                "name": name,
                "yield_pct": round(yield_val * 100, 2),
                "score": score,
                "status": "Sustainable" if is_sustainable else "Risky",
            })
        except Exception as e:
            skipped.append({"ticker": ticker, "reason": str(e)})

    return {"results": results, "skipped": skipped}
