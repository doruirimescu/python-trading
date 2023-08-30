import json
import re
from datetime import date
from enum import Enum
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel


class ValuationType(str, Enum):
    OVERVALUED = "Overvalued"
    UNDERVALUED = "Undervalued"


class Analysis(BaseModel):
    symbol: str
    valuation_type: ValuationType
    valuation_score: int
    solvency_score: int


def fetch_data_from_div(url, class_name):
    response = requests.get(url, timeout=15)
    response.raise_for_status()  # Raise an error for failed requests

    soup = BeautifulSoup(response.text, "html.parser")
    divs = soup.find_all("div", class_=class_name)

    if divs:
        return [div.get_text(strip=True) for div in divs]
    else:
        return ["No data found for the given class in divs."]


def fetch_data_from_paragraph(url, class_name):
    response = requests.get(url, timeout=15)
    response.raise_for_status()  # Raise an error for failed requests

    soup = BeautifulSoup(response.text, "html.parser")
    paragraphs = soup.find_all("p", class_=class_name)
    if paragraphs:
        return [paragraph.get_text(strip=True) for paragraph in paragraphs]
    else:
        return ["No data found for the given class in a paragraph."]


def get_solvency_score(url):
    profitability_class_name = "mobile-hidden block-desc"
    extracted_data = fetch_data_from_paragraph(url, profitability_class_name)
    extracted_data = [line.replace("\t", "") for line in extracted_data][1]
    profitability_score = extracted_data.split("\n")[1]

    # Remove the pattern /100 from the string
    profitability_score = profitability_score.replace("/100.", "")
    # convert to int
    profitability_score = int(profitability_score)
    return profitability_score


def get_valuation_score(url) -> Tuple[ValuationType, int]:
    valuation_class_name = "sixteen wide column"
    extracted_data = fetch_data_from_div(url, valuation_class_name)

    extracted_data = [line.replace("\t", "") for line in extracted_data]
    extracted_data = [line for line in extracted_data if "%." in line]
    if not extracted_data:
        raise ValueError("No data found for the given class in divs.")

    extracted_data = extracted_data[0]

    pattern = re.compile(r"(Overvalued by|Undervalued by)\s+(\d+%)")
    match = pattern.search(extracted_data)

    value_extracted = match.group(0) if match else "No match found"
    valuation = int(value_extracted.split()[2].replace("%", ""))
    if "Overvalued" in value_extracted:
        return (ValuationType.OVERVALUED, valuation)
    elif "Undervalued" in value_extracted:
        return (ValuationType.UNDERVALUED, valuation)
    else:
        raise ValueError("No match found for the pattern.")


def analyze_url(url: str, symbol: str) -> Analysis:
    print(f"Analyzing {symbol}...")
    valuation, score = get_valuation_score(url)
    solvency_score = get_solvency_score(url)
    print(f"Symbol: {symbol} is {valuation} by {score}% solvency: {solvency_score}")
    return Analysis(
        symbol=symbol,
        valuation_type=valuation,
        valuation_score=score,
        solvency_score=solvency_score,
    )
