import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import json as json_lib
import time

from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from loan.loan_vs_investment import perform_simulation
from loan.loan import LoanJsonParser
from stock.pvgo_calculator import calculate_pvgo
from stock.iv_15 import fetch_iv15_fundamentals, compute_iv15
from stock.yf_stock.dividend_sustainability import get_data, analyze_dividend_sustainability

app = FastAPI()

_cache: dict = {}
_CACHE_TTL = 1800  # 30 minutes
# Errors (mostly Yahoo rate limits) are cached briefly so retry-clicks
# don't keep hammering Yahoo and prolong the block on this server's IP.
_ERROR_TTL = 120

def _cache_get(key):
    entry = _cache.get(key)
    if entry and (time.time() - entry[1]) < entry[2]:
        return entry[0]
    return None

def _cache_set(key, value, ttl=_CACHE_TTL):
    _cache[key] = (value, time.time(), ttl)


def verify_token(x_api_token: str = Header(default="")):
    expected = os.getenv("API_TOKEN")
    if expected and x_api_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

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
    _: None = Depends(verify_token),
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
async def loan_analyze(file: UploadFile = File(...), _: None = Depends(verify_token)):
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
    _: None = Depends(verify_token),
):
    # manual_sbc is accepted in dollars; frontend sends millions * 1e6
    # The Yahoo fetch only depends on the ticker, so it is cached per ticker
    # and the DCF math is recomputed per request — changing growth/multiple/SBC
    # assumptions never triggers a new Yahoo call.
    symbol = ticker.upper()
    key = ('iv15-fundamentals', symbol)
    fundamentals = _cache_get(key)
    if fundamentals is None:
        fundamentals = fetch_iv15_fundamentals(symbol)
        _cache_set(key, fundamentals, ttl=_ERROR_TTL if isinstance(fundamentals, str) else _CACHE_TTL)
    if isinstance(fundamentals, str):
        return {"error": fundamentals}
    result = compute_iv15(fundamentals, symbol, growth_rate, terminal_multiple, manual_sbc)
    if isinstance(result, str):
        return {"error": result}
    return result


@app.get("/pvgo/calculate")
def pvgo_calculate(ticker: str, market_risk_premium: float = 0.05, _: None = Depends(verify_token)):
    key = ('pvgo', ticker.upper(), market_risk_premium)
    cached = _cache_get(key)
    if cached is not None:
        return {"error": cached} if isinstance(cached, str) else cached
    result = calculate_pvgo(ticker, market_risk_premium)
    if isinstance(result, str):
        _cache_set(key, result, ttl=_ERROR_TTL)
        return {"error": result}
    _cache_set(key, result)
    return result


@app.get("/dividend/sustainability")
def dividend_sustainability(tickers: str, threshold: int = 65, _: None = Depends(verify_token)):
    ticker_list = [t.strip().upper() for t in tickers.replace("\n", ",").split(",") if t.strip()]
    key = ('dividend', tuple(sorted(ticker_list)), threshold)
    cached = _cache_get(key)
    if cached is not None:
        return cached

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

    response = {"results": results, "skipped": skipped}
    _cache_set(key, response)
    return response
