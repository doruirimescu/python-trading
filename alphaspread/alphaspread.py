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
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for failed requests

    soup = BeautifulSoup(response.text, "html.parser")
    divs = soup.find_all("div", class_=class_name)

    if divs:
        return [div.get_text(strip=True) for div in divs]
    else:
        return ["No data found for the given class in divs."]


def fetch_data_from_paragraph(url, class_name):
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for failed requests

    soup = BeautifulSoup(response.text, "html.parser")
    paragraph_data = soup.find("p", class_=class_name)

    if paragraph_data:
        return paragraph_data.get_text(strip=True)
    else:
        return "No data found for the given class in a paragraph."


def get_solvency_score(url):
    profitability_class_name = "mobile-hidden block-desc"
    extracted_data = fetch_data_from_paragraph(url, profitability_class_name)
    extracted_data = extracted_data.split("\n")
    for i, line in enumerate(extracted_data):
        extracted_data[i] = line.strip()
        extracted_data[i] = line.replace("\t", "")
    # Search for pattern /100 in list
    profitability_score = [s for s in extracted_data if "/100" in s][0]
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
    print(f"Symbol: {symbol} is undervalued by {score}% solvency: {solvency_score}")
    return Analysis(
        symbol=symbol,
        valuation_type=valuation,
        valuation_score=score,
        solvency_score=solvency_score,
    )


def get_nasdaq_symbols() -> List:
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    }
    res = requests.get(
        "https://api.nasdaq.com/api/quote/list-type/nasdaq100", headers=headers
    )
    main_data = res.json()["data"]["data"]["rows"]
    symbols = []
    for i in range(len(main_data)):
        symbols.append(main_data[i]["symbol"])
    return symbols


if __name__ == "__main__":
    nasdaq_symbols = get_nasdaq_symbols()
    undervalued_symbols = []
    for symbol in nasdaq_symbols:
        url = f"https://www.alphaspread.com/security/nasdaq/{symbol}/summary"
        analysis = analyze_url(url, symbol)
        undervalued_symbols.append(analysis)

    date_today = date.today()
    file_name = f"nasdaq_analysis_{date_today}.json"
    with open(file_name, "w") as f:
        json_str = json.dumps(
            [analysis.dict() for analysis in undervalued_symbols], indent=4
        )
        f.write(json_str)
