import json
from datetime import date
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
import os


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


class LoanJsonParser:
    def __init__(self, json_path: str = "loan.json") -> None:
        self.CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))
        self.LOAN_DATA = load_data(self.CURRENT_FILE_PATH.joinpath(json_path))

    def add_payment(self, payment: Payment, json_data: Optional[dict] = None) -> None:
        if not json_data:
            json_data = self.LOAN_DATA
        json_data["history"].append(payment.__dict__)
        with open(self.LOAN_DATA, "w") as f:
            json.dump(json_data, f, indent=4, sort_keys=True, default=str)

    def combine_loans_same_date(self, loans: List[Payment]) -> Payment:
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

    def history_as_loans(self, json_data: Optional[dict] = None) -> List[Payment]:
        if json_data is None:
            json_data = self.LOAN_DATA
        results = list()
        data = json_data["history"]
        for loan in data:
            results.append(Payment(**loan))
        return results

    def loan_history(self, json_data: Optional[dict] = None) -> List[Payment]:
        if json_data is None:
            json_data = self.LOAN_DATA
        loans = self.history_as_loans(json_data)
        loans_by_date = dict()
        for loan in loans:
            year_month = (loan.date.year, loan.date.month)
            if year_month not in loans_by_date:
                loans_by_date[year_month] = list()
            loans_by_date[year_month].append(loan)
        # combine loans with same date
        results = list()
        for _, loans in loans_by_date.items():
            results.append(self.combine_loans_same_date(loans))
            # replace date with year, month
            d = results[-1].date
            results[-1].date.replace(year=d.year, month=d.month, day=1)
        return results

    def cost_paid(self, json_data: Optional[dict] = None) -> float:
        if json_data is None:
            json_data = self.LOAN_DATA
        history = json_data["history"]
        total_cost = 0
        for loan in history:
            total_cost += loan["cost"]
        return round(total_cost, 3)

    def get_interest_rate(self, json_data: Optional[dict] = None) -> float:
        if json_data is None:
            json_data = self.LOAN_DATA
        return json_data["interest_rate"]

    def principal_total(self, json_data: Optional[dict] = None) -> float:
        if json_data is None:
            json_data = self.LOAN_DATA
        return json_data["total"]

    def principal_paid(self, json_data: Optional[dict] = None) -> float:
        if json_data is None:
            json_data = self.LOAN_DATA
        total_principal = 0
        for d in json_data["history"]:
            total_principal += d["principal"]
        return round(total_principal, 3)

    def cumulative_principal_paid(self, json_data: Optional[dict] = None) -> List[Payment]:
        if json_data is None:
            json_data = self.LOAN_DATA
        loans = self.history_as_loans(json_data)
        loans_by_date = dict()
        for loan in loans:
            year_month = (loan.date.year, loan.date.month)
            if year_month not in loans_by_date:
                loans_by_date[year_month] = list()
            loans_by_date[year_month].append(loan)
        # combine loans with same date
        results = list()
        for _, loans in loans_by_date.items():
            results.append(self.combine_loans_same_date(loans))
            # replace date with year, month
            d = results[-1].date
            results[-1].date.replace(year=d.year, month=d.month, day=1)

        cumulative_principal = 0
        for loan in results:
            cumulative_principal += loan.principal
            loan.principal = cumulative_principal
        return results

    def interest_paid(self, json_data: Optional[dict] = None) -> float:
        if json_data is None:
            json_data = self.LOAN_DATA
        total_interest = 0
        for loan in json_data["history"]:
            total_interest += loan["interest"]
        print(total_interest)
        return round(total_interest, 3)

    def data_on_date(self, date: date, json_data: Optional[dict] = None) -> List[Payment]:
        if json_data is None:
            json_data = self.LOAN_DATA
        history = self.history_as_loans(json_data)
        # filter history by date
        return self.combine_loans_same_date([loan for loan in history if loan.date == date])

    def data_on_month_year(
        self,
        month: int, year: int, json_data: Optional[dict] = None
    ) -> List[Payment]:
        if json_data is None:
            json_data = self.LOAN_DATA
        history = self.history_as_loans(json_data)
        # filter history by month
        return self.combine_loans_same_date(
            [
                loan
                for loan in history
                if loan.date.month == month and loan.date.year == year
            ]
        )

    def get_monthly_installment(self, json_data: Optional[dict] = None) -> float:
        if json_data is None:
            json_data = self.LOAN_DATA
        return json_data["monthly_installment"]
