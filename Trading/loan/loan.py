import json
from datetime import date
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
from pathlib import Path
import os

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))


class Payment(BaseModel):
    date: date
    principal: float
    interest: float
    cost: float

    def __str__(self):
        return f"Date: {self.date} Principal: {self.principal:.2f} Interest: {self.interest} Cost: {self.cost}"


def load_data(filename: Path | str) -> List[Payment]:
    with open(filename) as f:
        data = json.load(f)
    return data


LOAN_DATA = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))

def add_payment(payment: Payment, json_data: dict = LOAN_DATA) -> None:
    print(payment.__dict__)
    json_data["history"].append(payment.__dict__)
    with open(CURRENT_FILE_PATH.joinpath("loan.json"), "w") as f:
        json.dump(json_data, f, indent=4, sort_keys=True, default=str)

def combine_loans_same_date(loans: List[Payment]) -> Payment:
    total_principal = 0
    total_interest = 0
    total_cost = 0
    for loan in loans:
        total_principal += loan.principal
        total_interest += loan.interest
        total_cost += loan.cost

    return Payment(
        date=loans[0].date,
        principal=total_principal,
        interest=total_interest,
        cost=total_cost,
    )


def history_as_loans(json_data: dict = LOAN_DATA) -> List[Payment]:
    results = list()
    data = json_data["history"]
    for loan in data:
        results.append(Payment(**loan))
    return results


def loan_history(json_data: Optional[dict] = None) -> List[Payment]:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    loans = history_as_loans(json_data)
    loans_by_date = dict()
    for loan in loans:
        year_month = (loan.date.year, loan.date.month)
        if year_month not in loans_by_date:
            loans_by_date[year_month] = list()
        loans_by_date[year_month].append(loan)
    # combine loans with same date
    results = list()
    for _, loans in loans_by_date.items():
        results.append(combine_loans_same_date(loans))
        # replace date with year, month
        d = results[-1].date
        results[-1].date.replace(year=d.year, month=d.month, day=1)
    return results


def cost_paid(json_data: Optional[dict] = None) -> float:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    history = json_data["history"]
    total_cost = 0
    for loan in history:
        total_cost += loan["cost"]
    return round(total_cost, 3)

def get_interest_rate(json_data: Optional[dict] = None) -> float:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    return json_data["interest_rate"]


def principal_total(json_data: Optional[dict] = None) -> float:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    return json_data["total"]


def principal_paid(json_data: Optional[dict] = None) -> float:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    total_principal = 0
    for d in json_data["history"]:
        total_principal += d["principal"]
    return round(total_principal, 3)

def cumulative_principal_paid(json_data: Optional[dict] = None) -> List[Payment]:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    loans = history_as_loans(json_data)
    loans_by_date = dict()
    for loan in loans:
        year_month = (loan.date.year, loan.date.month)
        if year_month not in loans_by_date:
            loans_by_date[year_month] = list()
        loans_by_date[year_month].append(loan)
    # combine loans with same date
    results = list()
    for _, loans in loans_by_date.items():
        results.append(combine_loans_same_date(loans))
        # replace date with year, month
        d = results[-1].date
        results[-1].date.replace(year=d.year, month=d.month, day=1)

    cumulative_principal = 0
    for loan in results:
        cumulative_principal += loan.principal
        loan.principal = cumulative_principal
    return results


def interest_paid(json_data: Optional[dict] = None) -> float:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    total_interest = 0
    for loan in json_data["history"]:
        total_interest += loan["interest"]
    print(total_interest)
    return round(total_interest, 3)


def data_on_date(date: date, json_data: dict = LOAN_DATA) -> List[Payment]:
    results = list()
    history = history_as_loans(json_data)
    # filter history by date
    return combine_loans_same_date([loan for loan in history if loan.date == date])


def data_on_month_year(
    month: int, year: int, json_data: dict = LOAN_DATA
) -> List[Payment]:
    results = list()
    history = history_as_loans(json_data)
    # filter history by month
    return combine_loans_same_date(
        [
            loan
            for loan in history
            if loan.date.month == month and loan.date.year == year
        ]
    )

def get_monthly_installment(json_data: Optional[dict] = None) -> float:
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))
    return json_data["monthly_installment"]
