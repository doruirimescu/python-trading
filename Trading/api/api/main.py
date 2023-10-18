from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
import Trading.loan.loan as loan
from Trading.loan.routes.loan_routes import router as loan_router
from Trading.investment.routes.investment_routes import router as investment_router
from Trading.stock.routes.stock_routes import router as stock_router
load_dotenv()

app = FastAPI()
app.include_router(router=loan_router, prefix="/loan")
app.include_router(router=investment_router, prefix="/investment")
app.include_router(router=stock_router, prefix="/stock")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
orchestrators_dict = {}
sid_username_dict = {}


@app.get("/")
def read_root():
    return {"Hello": "World"}
