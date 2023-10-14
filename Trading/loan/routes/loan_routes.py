from fastapi import APIRouter
import Trading.loan.loan as loan
import Trading.loan.loan_vs_investment as loan_vs_investment

router = APIRouter()


@router.post("/history")
def add_payment(payment: loan.Payment):
    return loan.add_payment(payment)


@router.get("/history")
def loan_history():
    return loan.loan_history()


@router.get("/total/principal_paid")
def principal_paid():
    return {"total_principal_paid": loan.principal_paid()}


@router.get("/cumulative/principal_paid")
def principal_paid():
    return loan.cumulative_principal_paid()


@router.get("/total/interest_paid")
def interest_paid():
    return {"value": loan.interest_paid()}


@router.get("/total/cost_paid")
def cost_paid():
    return {"value": loan.cost_paid()}


@router.get("/total/principal")
def total_principal():
    return {"value": loan.principal_total()}


@router.get("/interest_rate")
def interest_rate():
    return {"value": loan.get_interest_rate()}


@router.get("/loan_vs_investment")
def interest_rate(
    investment_return: float,
    yearly_salary: int,
    n_years: int,
    should_plot: bool = False,
):
    fixed_monthly_installement = loan.get_monthly_installment()
    principal = loan.principal_total() - loan.principal_paid()
    interest_rate = loan.get_interest_rate() / 100.0
    investment_return = investment_return / 100.0

    return loan_vs_investment.perform_simulation(
        principal,
        interest_rate,
        fixed_monthly_installement,
        investment_return,
        yearly_salary,
        n_years,
        should_plot=False,
    )
