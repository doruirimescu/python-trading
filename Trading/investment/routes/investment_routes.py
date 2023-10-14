from fastapi import APIRouter
from Trading.investment.investment import get_progress, get_target_rate
router = APIRouter()

@router.get("/progress")
def get_get_progress():
    return {"value": get_progress()}

@router.get("/target/rate")
def get_get_progress():
    return {"value": get_target_rate()}
