import asyncio
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from bs4 import BeautifulSoup
import requests
import asyncio
import aiohttp
from typing import List, Dict

HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def load_html(url) -> str:
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

def to_beautiful_soup(url: str) -> BeautifulSoup:
    html = load_html(url)
    return BeautifulSoup(html, "html.parser")


async def download_rendered_html_async(
    url: str,
    filename: str,
    *,
    wait_selector: str = "body",
    timeout_ms: int = 15000,
    user_agent: str = DEFAULT_UA,
    storage_state: Optional[str] = None,
    block_images: bool = True,
    take_screenshot: bool = False,
) -> str:
    """
    Render `url` in a headless browser and write the resulting HTML to `filename`.
    Returns the saved filename.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=user_agent,
            java_script_enabled=True,
            storage_state=storage_state if storage_state else None,
        )

        if block_images:
            await context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in {"image"}
                    else route.continue_()
                ),
            )

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_selector(wait_selector, timeout=timeout_ms)
            html = await page.content()
            Path(filename).write_text(html, encoding="utf-8")
            if take_screenshot:
                await page.screenshot(
                    path=str(Path(filename).with_suffix(".png")), full_page=True
                )
            return filename
        finally:
            await page.close()
            await context.close()
            await browser.close()


import asyncio
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# Helper: render a URL in Playwright and return (url, soup|None)
async def to_beautiful_soup_rendered_async(
    context,
    url: str,
    *,
    wait_selector: str = "body",
    timeout_ms: int = 15000,
) -> Tuple[str, Optional[BeautifulSoup]]:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_selector(wait_selector, timeout=timeout_ms)
        html = await page.content()
        return url, BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"[to_beautiful_soup_rendered_async] Failed for {url}: {e}")
        return url, None
    finally:
        await page.close()


# Matches your signature & return type
async def gather_rendered_html(
    urls: List[str], concurrency: int = 10
) -> Dict[str, BeautifulSoup]:
    """
    Concurrently render the given URLs (headless browser) and parse into BeautifulSoup.
    Returns {url: soup} for successes (failed URLs are omitted).
    """
    sem = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=DEFAULT_UA,
            java_script_enabled=True,
        )

        async def task(url: str):
            async with sem:
                return await to_beautiful_soup_rendered_async(context, url)

        results = await asyncio.gather(*(task(u) for u in urls))
        await context.close()
        await browser.close()

    # Match your gather_soups return style
    return {url: soup for url, soup in results if soup is not None}

def scrape_urls_async(urls: List[str], concurrency: int = 10) -> Dict[str, BeautifulSoup]:
    return asyncio.run(gather_rendered_html(urls, concurrency))

from playwright.sync_api import sync_playwright
def download_rendered_html(url: str, filename: str, wait_selector: str = "body"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(  # sends realistic headers; handles cookies
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36)"),
                java_script_enabled=True,
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector(wait_selector, timeout=15000)
            html = page.content()
            Path(filename).write_text(html, encoding="utf-8")
            return filename
        finally:
            browser.close()
