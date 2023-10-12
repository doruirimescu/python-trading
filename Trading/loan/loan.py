import json
from datetime import date
from typing import List
from pydantic import BaseModel
from pathlib import Path
from pathlib import Path
import os

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))


class Loan(BaseModel):
    date: date
    principal: float
    interest: float
    cost: float

    def __str__(self):
        return f"Date: {self.date} Principal: {self.principal:.2f} Interest: {self.interest} Cost: {self.cost}"

def load_data(filename: Path | str) -> List[Loan]:
    with open(filename) as f:
        data = json.load(f)
    return data

LOAN_DATA = load_data(CURRENT_FILE_PATH.joinpath("loan.json"))

def combine_loans_same_date(loans: List[Loan]) -> Loan:
    total_principal = 0
    total_interest = 0
    total_cost = 0
    for loan in loans:
        total_principal += loan.principal
        total_interest += loan.interest
        total_cost += loan.cost

    return Loan(date=loans[0].date, principal=total_principal, interest=total_interest, cost=total_cost)


def history_as_loans(json_data: dict = LOAN_DATA) -> List[Loan]:
    results = list()
    data = json_data['history']
    for loan in data:
        results.append(Loan(**loan))
    return results

def loan_history(json_data: dict = LOAN_DATA) -> List[Loan]:
    loans = history_as_loans(json_data)
    loans_by_date = dict()
    for loan in loans:
        if loan.date not in loans_by_date:
            loans_by_date[loan.date] = list()
        loans_by_date[loan.date].append(loan)
    # combine loans with same date
    results = list()
    for date, loans in loans_by_date.items():
        results.append(combine_loans_same_date(loans))
    return results


def cost_paid(json_data: dict = LOAN_DATA) -> float:
    history = json_data['history']
    total_cost = 0
    for loan in history:
        total_cost += loan['cost']
    return round(total_cost, 3)

def principal_total(json_data: dict = LOAN_DATA) -> float:
    return json_data['total']

def principal_paid(json_data: dict = LOAN_DATA) -> float:
    total_principal = 0
    for d in json_data['history']:
        total_principal += d['principal']
    return round(total_principal, 3)


def interest_paid(json_data: dict = LOAN_DATA) -> float:
    total_interest = 0
    for loan in json_data['history']:
        total_interest += loan['interest']
    return round(total_interest, 3)


def data_on_date(date: date, json_data: dict = LOAN_DATA) -> List[Loan]:
    results = list()
    history = history_as_loans(json_data)
    # filter history by date
    return combine_loans_same_date([loan for loan in history if loan.date == date])

def data_on_month_year(month: int, year: int, json_data: dict = LOAN_DATA) -> List[Loan]:
    results = list()
    history = history_as_loans(json_data)
    # filter history by month
    return combine_loans_same_date([loan for loan in history
                          if loan.date.month == month and
                          loan.date.year == year])
