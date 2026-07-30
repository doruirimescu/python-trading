# gurufocus_search.py
from __future__ import annotations

import re
import time
from typing import List, Optional, Tuple
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SEARCH_URL = "https://www.gurufocus.com/search?s={q}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0 Safari/537.36"
    )
}

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()

def _extract_candidates_from_html(html: str, base_url: str = "https://www.gurufocus.com/") -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    found: List[Tuple[str, str]] = []
    for a in soup.select('a[href*="/stock/"]'):
        href = a.get("href") or ""
        text = a.get_text(" ", strip=True)
        if href.startswith("/"):
            href = urljoin(base_url, href)
        if href.endswith("/dcf"):
            href = href[:-3] + "summary"
        if href.endswith("/summary"):
            found.append((href, text))
    # de-dupe, keep order
    seen = set()
    uniq = []
    for item in found:
        if item[0] not in seen:
            seen.add(item[0])
            uniq.append(item)
    return uniq

def _score(company_name: str, href_text: Tuple[str, str]) -> int:
    href, text = href_text
    target = _normalize(company_name)
    t = _normalize(text)
    score = 0
    if t == target:
        score += 3
    if target and target in t:
        score += 2
    if re.search(r"/stock/[A-Za-z\.\-]+/summary$", href):
        score += 1
    if not t:
        score -= 1
    return score

def _pick_best(company_name: str, candidates: List[Tuple[str, str]]) -> Optional[str]:
    if not candidates:
        return None
    candidates.sort(key=lambda it: _score(company_name, it), reverse=True)
    return candidates[0][0]

def find_summary_link(company_name: str, *, timeout_ms: int = 30000) -> Optional[str]:
    """
    Resolve a GuruFocus '/stock/<TICKER>/summary' link for the given company name.

    Simple standalone API – manages its own browser lifecycle.

    Returns:
        str URL or None if not found.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        try:
            url = SEARCH_URL.format(q=quote(company_name))
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Let the client-side hydration settle; try a few short cycles.
            # GuruFocus's search page keeps background network activity going
            # (analytics/ads), so it may never reach "networkidle" - that's
            # fine, the selector-polling loop below is what actually matters.
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms // 2)
            except PlaywrightTimeoutError:
                pass

            candidates: List[Tuple[str, str]] = []
            for _ in range(4):
                try:
                    # If links aren’t there yet, wait a bit more.
                    page.wait_for_selector('a[href*="/stock/"]', timeout=6000)
                except PlaywrightTimeoutError:
                    page.wait_for_load_state("networkidle", timeout=6000)

                html = page.content()
                candidates = _extract_candidates_from_html(html)
                if candidates:
                    break
                time.sleep(1.25)

            return _pick_best(company_name, candidates)
        finally:
            context.close()
            browser.close()

# Optional: use this when resolving many companies to reuse one browser for speed
class GFSummaryResolver:
    def __init__(self, *, headless: bool = True):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._headless = headless

    def __enter__(self) -> "GFSummaryResolver":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self._headless, args=["--disable-blink-features=AutomationControlled"]
        )
        self._context = self._browser.new_context(user_agent=HEADERS["User-Agent"])
        self._page = self._context.new_page()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def find_summary_link(self, company_name: str, *, timeout_ms: int = 30000) -> Optional[str]:
        url = SEARCH_URL.format(q=quote(company_name))
        page = self._page
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms // 2)
        except PlaywrightTimeoutError:
            pass

        candidates: List[Tuple[str, str]] = []
        for _ in range(4):
            try:
                page.wait_for_selector('a[href*="/stock/"]', timeout=6000)
            except PlaywrightTimeoutError:
                page.wait_for_load_state("networkidle", timeout=6000)

            html = page.content()
            candidates = _extract_candidates_from_html(html)
            if candidates:
                break
            time.sleep(1.25)

        return _pick_best(company_name, candidates)
