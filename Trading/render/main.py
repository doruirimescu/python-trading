import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loan.loan_vs_investment import perform_simulation
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


@app.get("/pvgo/calculate")
def pvgo_calculate(ticker: str, market_risk_premium: float = 0.05):
    result = calculate_pvgo(ticker, market_risk_premium)
    if isinstance(result, str):
        return {"error": result}
    return result
