from fastapi import APIRouter
import Trading.loan.loan as loan

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
