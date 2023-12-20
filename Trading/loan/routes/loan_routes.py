from fastapi import APIRouter
import Trading.loan.loan as loan
import Trading.loan.loan_vs_investment as loan_vs_investment

router = APIRouter()
ljp = loan.LoanJsonParser()


@router.post("/history")
def add_payment(payment: loan.Payment):
    return ljp.add_payment(payment)


@router.get("/history")
def loan_history():
    return ljp.loan_history()


@router.get("/total/principal_paid")
def principal_paid():
    return {"total_principal_paid": ljp.principal_paid()}


@router.get("/cumulative/principal_paid")
def principal_paid():
    return ljp.cumulative_principal_paid()


@router.get("/total/interest_paid")
def interest_paid():
    return {"value": ljp.interest_paid()}


@router.get("/total/cost_paid")
def cost_paid():
    return {"value": ljp.cost_paid()}


@router.get("/total/principal")
def total_principal():
    return {"value": ljp.principal_total()}


@router.get("/interest_rate")
def interest_rate():
    return {"value": ljp.get_interest_rate()}


@router.get("/loan_vs_investment")
def interest_rate(
    investment_return: float,
    yearly_salary: int,
    n_years: int,
    should_plot: bool = False,
):
    fixed_monthly_installement = ljp.get_monthly_installment()
    principal = ljp.principal_total() - ljp.principal_paid()
    interest_rate = ljp.get_interest_rate() / 100.0
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
