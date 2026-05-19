import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import json as json_lib

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from loan.loan_vs_investment import perform_simulation
from loan.loan import LoanJsonParser
from stock.pvgo_calculator import calculate_pvgo

app = FastAPI()

# --- CRITICAL STEP: CORS Configuration ---
# Replace the URL below with your actual GitHub Pages URL
origins = [
    "https://doruirimescu.github.io"
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
        {"date": str(p.date), "principal": p.principal, "interest": p.interest, "cost": p.cost}
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
    interest_rate = parser.get_interest_rate(loan_data)
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


@app.get("/pvgo/calculate")
def pvgo_calculate(ticker: str, market_risk_premium: float = 0.05):
    result = calculate_pvgo(ticker, market_risk_premium)
    if isinstance(result, str):
        return {"error": result}
    return result
