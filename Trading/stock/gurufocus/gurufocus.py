import re
from Trading.utils.html import to_beautiful_soup
from stateful_data_processor.processor import StatefulDataProcessor
from pydantic import BaseModel


class GurufocusAnalysis(BaseModel):
    company_name: str = None
    ticker: str = None
    market_cap: str = None
    financial_strength: float = None
    piotroski_f_score: float = None
    gf_value_rank: float = None
    gf_value: float = None
    altman_z_score: float = None


MARKET_CAP_REGEX = re.compile(
    r"Market Cap\s*[:\-]?\s*\$?\s*([\d\.]+\s*[MBT]?)", re.IGNORECASE
)


def extract_stock_info(html: str) -> GurufocusAnalysis:
    soup = to_beautiful_soup(html)

    data = {
        "company_name": None,
        "ticker": None,
        "market_cap": None,
        "financial_strength": None,
        "piotroski_f_score": None,
        "gf_value_rank": None,
        "gf_value": None,
        "altman_z_score": None,
    }

    # --- Extract Company Name and Ticker ---
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text()
        if "(" in title_text and ")" in title_text:
            name_part, ticker_part = title_text.split("(")
            data["company_name"] = name_part.strip()
            data["ticker"] = ticker_part.split(")")[0].strip()

    # --- Extract Market Cap using text-based search ---
    full_text = soup.get_text(separator=" ", strip=True)
    mc_match = MARKET_CAP_REGEX.search(full_text)
    if mc_match:
        data["market_cap"] = mc_match.group(1).strip()

    # --- Extract Financial Strength ---
    for header in soup.find_all("h2"):
        if "Financial Strength" in header.get_text(strip=True):
            parent = header.find_next("div", class_="flex flex-center")
            if parent:
                score_span = parent.find("span", class_="t-default bold")
                if score_span:
                    try:
                        data["financial_strength"] = float(
                            score_span.get_text(strip=True)
                        )
                    except ValueError:
                        pass
            break

    # --- Extract GF Value Rank ---
    for header in soup.find_all("h2"):
        if "GF Value Rank" in header.get_text(strip=True):
            parent = header.find_next("div", class_="flex flex-center")
            if parent:
                score_span = parent.find("span", class_="t-default bold")
                if score_span:
                    try:
                        data["gf_value_rank"] = float(score_span.get_text(strip=True))
                    except ValueError:
                        pass
            break

    # --- Piotroski F-Score ---
    for td in soup.find_all("td"):
        if "Piotroski F-Score" in td.get_text(strip=True):
            next_td = td.find_next_sibling("td")
            if next_td:
                score_span = next_td.find("span", class_="p-l-sm")
                if score_span:
                    try:
                        data["piotroski_f_score"] = float(
                            score_span.get_text(strip=True).split("/")[0].strip()
                        )
                    except ValueError:
                        pass
            break

    # --- Extract GF Value ---
    for header in soup.find_all("h2"):
        if "GF Value:" in header.get_text(strip=True):
            value_span = header.find_next("span", class_="t-primary")
            if value_span:
                try:
                    data["gf_value"] = float(
                        value_span.get_text(strip=True).replace("$", "")
                    )
                except ValueError:
                    pass
            break

    # --- Extract Altman Z-Score ---
    for td in soup.find_all("td"):
        if "Altman Z-Score" in td.get_text(strip=True):
            next_td = td.find_next_sibling("td")
            if next_td:
                score_span = next_td.find("span", class_="p-l-sm")
                if score_span:
                    try:
                        data["altman_z_score"] = float(score_span.get_text(strip=True))
                    except ValueError:
                        pass
            break

    return GurufocusAnalysis(**data)


class GurufocusAnalyzer(StatefulDataProcessor):
    def __init__(self, json_file_writer=None, logger=None):
        super().__init__(json_file_writer, logger=logger)
        self.data = {}

    def process_item(self, item, iteration_index, data):
        url = item
        stock_info = extract_stock_info(url)
        self.data[stock_info.ticker] = stock_info.dict()
