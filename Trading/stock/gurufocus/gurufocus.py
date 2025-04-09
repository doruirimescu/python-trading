import requests
from bs4 import BeautifulSoup

def download_html(url, filename='gurufocus_page.html'):
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(response.text)

    return filename

from bs4 import BeautifulSoup
import re

def extract_stock_info(html_file_path):
    with open(html_file_path, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    data = {
        "company_name": None,
        "ticker": None,
        "market_cap": None,
        "financial_strength": None,
        "piotroski_f_score": None
    }

    # Extract from title
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text()
        if "(" in title_text and ")" in title_text:
            name_part, ticker_part = title_text.split("(")
            data["company_name"] = name_part.strip()
            data["ticker"] = ticker_part.split(")")[0].strip()

    # Extract raw text from page
    full_text = soup.get_text(separator=' ', strip=True)

    # Extract market cap
    match = re.search(r"Market Cap\s*[:\-]?\s*\$?\s*([\d\.]+\s*[MBT]?)", full_text, re.IGNORECASE)
    if match:
        data["market_cap"] = match.group(1).strip()

    # --- Extract Financial Strength from div.flex.flex-center ---
    for header in soup.find_all("h2"):
        if "Financial Strength" in header.get_text(strip=True):
            parent = header.find_next("div", class_="flex flex-center")
            if parent:
                score_span = parent.find("span", class_="t-default bold")
                label_span = parent.find("span", class_="t-label")
                if score_span and label_span:
                    data["financial_strength"] = f"{score_span.get_text(strip=True)}{label_span.get_text(strip=True)}"
            break

    # --- Extract GF Value Rank ---
    for header in soup.find_all("h2"):
        if "GF Value Rank" in header.get_text(strip=True):
            parent = header.find_next("div", class_="flex flex-center")
            if parent:
                score_span = parent.find("span", class_="t-default bold")
                label_span = parent.find("span", class_="t-label")
                if score_span and label_span:
                    data["gf_value_rank"] = f"{score_span.get_text(strip=True)}{label_span.get_text(strip=True)}"
            break

    # --- Piotroski F-Score ---
    # Find <td> tag that contains "Piotroski F-Score"
    for td in soup.find_all("td"):
        if "Piotroski F-Score" in td.get_text(strip=True):
            next_td = td.find_next_sibling("td")
            if next_td:
                score_span = next_td.find("span", class_="p-l-sm")
                if score_span:
                    score_text = score_span.get_text(strip=True)
                    data["piotroski_f_score"] = score_text
            break
    # --- Extract GF Value ---
    for header in soup.find_all("h2"):
        if "GF Value:" in header.get_text(strip=True):
            value_span = header.find_next("span", class_="t-primary")
            if value_span:
                data["gf_value"] = value_span.get_text(strip=True)
            break
    # --- Extract Altman Z-Score ---
    for td in soup.find_all("td"):
        if "Altman Z-Score" in td.get_text(strip=True):
            next_td = td.find_next_sibling("td")
            if next_td:
                score_span = next_td.find("span", class_="p-l-sm")
                if score_span:
                    data["altman_z_score"] = score_span.get_text(strip=True)
            break
    return data

# Example usage
if __name__ == "__main__":
#     url = "https://www.gurufocus.com/stock/GOGL/summary"
# html_file = download_html(url)
# print(f"Downloaded HTML to {html_file}")
    html_path = "gurufocus_page.html"  # Adjust path if needed
    info = extract_stock_info(html_path)
    print(info)
