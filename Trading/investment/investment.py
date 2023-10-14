import json
from datetime import date
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
from pathlib import Path
import os

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))

def load_data(filename: Path | str):
    with open(filename) as f:
        data = json.load(f)
    return data

def get_total_invested(json_data: Optional[dict] = None):
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("us500.json"))
    total = 0
    for h in json_data["history"]:
        total += h['investment']
    return total

def get_target(json_data: Optional[dict] = None):
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("us500.json"))
    return json_data["target"]

def get_progress(json_data: Optional[dict] = None):
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("us500.json"))
    return 100 * get_total_invested(json_data) / get_target(json_data)

def get_target_rate(json_data: Optional[dict] = None):
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("us500.json"))
    time_remaining = (date.fromisoformat(json_data["target_date"]) - date.today())
    months_remaining = time_remaining.days / 30
    amount_remaining = get_target(json_data) - get_total_invested(json_data)
    return amount_remaining / months_remaining

def get_history(json_data: Optional[dict] = None):
    if json_data is None:
        json_data = load_data(CURRENT_FILE_PATH.joinpath("us500.json"))
    return json_data["history"]
