from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
import Trading.loan.loan as loan
from Trading.loan.routes.loan_routes import router
load_dotenv()

app = FastAPI()
app.include_router(router=router, prefix="/loan")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
orchestrators_dict = {}
sid_username_dict = {}


@app.get("/")
def read_root():
    return {"Hello": "World"}
