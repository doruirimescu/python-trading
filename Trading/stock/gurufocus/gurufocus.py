import requests
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict

@dataclass
class GurufocusAnalysis:
    company_name: str = None
    ticker: str = None
    market_cap: str = None
    financial_strength: float = None
    piotroski_f_score: float = None
    gf_value_rank: float = None
    gf_value: float = None
    altman_z_score: float = None

    def __iter__(self):
        return iter(asdict(self).items())
def download_html(url, filename="gurufocus_page.html"):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    with open(filename, "w", encoding="utf-8") as f:
        f.write(response.text)

    return filename



MARKET_CAP_REGEX = re.compile(
    r"Market Cap\s*[:\-]?\s*\$?\s*([\d\.]+\s*[MBT]?)", re.IGNORECASE
)
def extract_stock_info(html_file_path: str) -> GurufocusAnalysis:
    with open(html_file_path, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

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


# Example usage
# if __name__ == "__main__":
# #     url = "https://www.gurufocus.com/stock/GOGL/summary"
# # html_file = download_html(url)
# # print(f"Downloaded HTML to {html_file}")
#     html_path = "gurufocus_page.html"  # Adjust path if needed
#     info = extract_stock_info(html_path)
#     print(info)
