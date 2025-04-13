from bs4 import BeautifulSoup
import requests
import asyncio
import aiohttp
from typing import List, Dict

HEADERS = {"User-Agent": "Mozilla/5.0"}

def download_html(url, filename: str):
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    with open(filename, "w", encoding="utf-8") as f:
        f.write(response.text)

    return filename

def load_html(url) -> str:
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    return response.text

def to_beautiful_soup(url: str) -> BeautifulSoup:
    html = load_html(url)
    return BeautifulSoup(html, "html.parser")

async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url, headers=HEADERS, timeout=10) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return ""

async def to_beautiful_soup_async(session: aiohttp.ClientSession, url: str) -> tuple[str, BeautifulSoup | None]:
    html = await fetch_html(session, url)
    if html:
        return url, BeautifulSoup(html, "html.parser")
    return url, None

async def gather_soups(urls: List[str], concurrency: int = 10) -> Dict[str, BeautifulSoup]:
    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [to_beautiful_soup_async(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        return {url: soup for url, soup in results if soup is not None}

def scrape_urls_async(urls: List[str], concurrency: int = 10) -> Dict[str, BeautifulSoup]:
    return asyncio.run(gather_soups(urls, concurrency))
