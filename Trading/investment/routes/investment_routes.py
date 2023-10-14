from fastapi import APIRouter
import Trading.investment.investment as investment
router = APIRouter()

@router.get("/progress")
def get_get_progress():
    return {"value": investment.get_progress()}

@router.get("/target/rate")
def get_progress():
    return {"value": investment.get_target_rate()}

@router.get("/history")
def get_history():
    return {"value": investment.get_history()}
