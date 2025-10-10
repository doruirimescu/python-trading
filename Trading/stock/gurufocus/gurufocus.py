import re
from stateful_data_processor.processor import StatefulDataProcessor
from pydantic import BaseModel
from typing import Optional
from bs4 import BeautifulSoup


class GurufocusAnalysis(BaseModel):
    company_name: Optional[str] = None
    ticker: Optional[str] = None
    market_cap: Optional[str] = None
    financial_strength: Optional[float] = None
    piotroski_f_score: Optional[float] = None
    gf_value_rank: Optional[float] = None
    gf_value: Optional[float] = None
    altman_z_score: Optional[float] = None
    gf_score: Optional[float] = None


MARKET_CAP_REGEX = re.compile(
    r"Market Cap\s*[:\-]?\s*\$?\s*([\d\.]+\s*[MBT]?)", re.IGNORECASE
)

def extract_stock_info(soup: BeautifulSoup) -> GurufocusAnalysis:
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
        if "Symbol Lookup" in title_text:
            return None
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

    def process_item(self, item: str, soup: BeautifulSoup | str, iteration_index):
        self.logger.info(f"Item: {item}, soup length: {len(str(soup)) if soup else 'None'}")
        if isinstance(soup, str):
            soup = BeautifulSoup(soup, "html.parser")
        stock_info = extract_stock_info(soup)
        if stock_info is None or stock_info.ticker is None:
            # get only item title
            self.logger.warning(f"Could not extract ticker from item: {item}")
            return
        self.data[item] = stock_info.dict()
