import re
from enum import Enum
from typing import Tuple

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
    profitability_score: int

    def __str__(self) -> str:
        return (
            f"Symbol {self.symbol} is {self.valuation_type} by {self.valuation_score}%"
            f" with solvency: {self.solvency_score}% and profitability: {self.profitability_score}%."
        )


def fetch_data_from_url(url) -> requests.Response:
    response = requests.get(url, timeout=15)
    response.raise_for_status()  # Raise an error for failed requests
    return response


def fetch_data_from_div(response: requests.Response, class_name: str):
    soup = BeautifulSoup(response.text, "html.parser")
    divs = soup.find_all("div", class_=class_name)

    if divs:
        return [div.get_text(strip=True) for div in divs]
    else:
        return ["No data found for the given class in divs."]


def fetch_data_from_paragraph(response: requests.Response, class_name):
    soup = BeautifulSoup(response.text, "html.parser")
    paragraphs = soup.find_all("p", class_=class_name)
    if paragraphs:
        return [paragraph.get_text(strip=True) for paragraph in paragraphs]
    else:
        return ["No data found for the given class in a paragraph."]


def get_solvency_score(response: requests.Response):
    solvency_class_name = "mobile-hidden block-desc"
    extracted_data = fetch_data_from_paragraph(response, solvency_class_name)
    extracted_data = [line.replace("\t", "") for line in extracted_data][1]
    solvency_score = extracted_data.split("\n")[1]

    # Remove the pattern /100 from the string
    solvency_score = solvency_score.replace("/100.", "")
    # convert to int
    solvency_score = int(solvency_score)
    return solvency_score


def get_profitability_score(response: requests.Response):
    profitability_class_name = "mobile-hidden block-desc"
    extracted_data = fetch_data_from_paragraph(response, profitability_class_name)
    profitability_score = [line.replace("\t", "") for line in extracted_data][0]
    profitability_score = profitability_score.split("\n")[1]

    # Remove the pattern /100 from the string
    profitability_score = profitability_score.replace("/100.", "")

    # convert to int
    profitability_score = int(profitability_score)
    return profitability_score


def get_valuation_score(response: requests.Response) -> Tuple[ValuationType, int]:
    valuation_class_name = "sixteen wide column"
    extracted_data = fetch_data_from_div(response, valuation_class_name)

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
    response = fetch_data_from_url(url)
    valuation, score = get_valuation_score(response)
    solvency_score = get_solvency_score(response)
    profitability_score = get_profitability_score(response)
    return Analysis(
        symbol=symbol,
        valuation_type=valuation,
        valuation_score=score,
        solvency_score=solvency_score,
        profitability_score=profitability_score
    )
