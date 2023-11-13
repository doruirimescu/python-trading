from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import os
import json

CURRENT_FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))
SILVER_FIlE_PATH = CURRENT_FILE_PATH.joinpath("silver.json")

def load_data(filename: Path | str):
    with open(filename) as f:
        data = json.load(f)
    return data


def get_total_invested(json_data: Optional[dict] = None):
    if json_data is None:
        json_data = load_data(SILVER_FIlE_PATH)
    total = 0
    for h in json_data["history"]:
        total += h['paid_price_eur']
    return total

class Type(str, Enum):
    coin = "coin",
    jewelry = "jewelry",
    tableware = "tableware",
    bullion = "bullion"

@dataclass
class Investment:
    type: Type
    name: str
    paid_price_eur: float
    original_silver_price_eur: float
    silver_content: float
    weight_g: float
    quantity: int
    date_purchased: Optional[datetime] = None

class Investments:
    def __init__(self, investments: List[Investment]) -> None:
        self.investments = investments

    def total_invested_eur(self):
        return sum([i.quantity * i.paid_price_eur for i in self.investments])

    def total_silver_weight_g(self):
        return sum([i.quantity * i.weight_g * i.silver_content for i in self.investments])

    def total_weight_g(self):
        return sum([i.quantity * i.weight_g for i in self.investments])

    def total_silver_ratio(self):
        return self.total_silver_weight_g() / self.total_weight_g()

    def average_price_per_gram(self):
        return sum([i.original_silver_price_eur for i in self.investments]) / len(self)

    def __len__(self):
        return len(self.investments)
    def summarize(self):
        print(f"Total invested: {self.total_invested_eur():.2f} EUR",
              f"Total silver weight: {self.total_silver_weight_g():.2f} g",
              f"Total weight: {self.total_weight_g():.2f} g",
              f"Total silver ratio: {self.total_silver_ratio():.2f}",
            f"Average price per gram: {self.average_price_per_gram():.3f} EUR/g",
              sep="\n")

def parse_data(json_data: Optional[dict] = None) -> List[Investment]:
    if json_data is None:
        json_data = load_data(SILVER_FIlE_PATH)
    investments = []
    for h in json_data["history"]:
        i = Investment(**h)
        investments.append(i)
    return Investments(investments)

inv = parse_data()
inv.summarize()
