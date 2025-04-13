from bs4 import BeautifulSoup
import requests

def download_html(url, filename: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    with open(filename, "w", encoding="utf-8") as f:
        f.write(response.text)

    return filename

def load_html(url) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.text

def to_beautiful_soup(url: str) -> BeautifulSoup:
    html = load_html(url)
    return BeautifulSoup(html, "html.parser")
