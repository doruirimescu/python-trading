"""GuruFocus-based valuation fetcher.

Replaces the Alphaspread-based fetch in analyze_nasdaq.py: Alphaspread now
serves a Cloudflare bot-challenge to every request regardless of User-Agent,
so plain `requests` scraping no longer works there at all. GuruFocus serves
the same kind of Cloudflare challenge, but Playwright's headless Chromium
(already used elsewhere in this repo, see Trading/utils/html_utils.py)
clears it reliably.

Produces the same Analysis schema (symbol, valuation_type, valuation_score,
solvency_score, profitability_score) the Alphaspread path did, so
visualize.py/summarize.py/filter_nasdaq_json.py need no changes.
"""
import re
from typing import Dict, List, Optional

from Trading.symbols.constants import GURUFOCUS_STOCK_SYMBOLS_DICT
from Trading.stock.gurufocus.gurufocus import extract_stock_info, to_valuation_analysis
from Trading.utils.custom_logging import get_logger
from Trading.utils.html_utils import scrape_urls_async

LOGGER = get_logger("gurufocus_valuation")

_PLAIN_TICKER_RE = re.compile(r"\(([^()]+)\)\s*$")


def _build_ticker_url_index() -> Dict[str, str]:
    """Reverse-index Trading/symbols/gurufocus/stocks.json by plain ticker
    (the part inside the parens when it has no "EXCHANGE:" prefix, e.g.
    "Apple Inc(AAPL)" -> "AAPL" -> its URL). A ticker that maps to more than
    one distinct URL is dropped rather than guessed at - we can't tell which
    company/exchange is the right one without more context.
    """
    index: Dict[str, str] = {}
    ambiguous = set()
    for key, url in GURUFOCUS_STOCK_SYMBOLS_DICT.items():
        m = _PLAIN_TICKER_RE.search(key)
        if not m:
            continue
        ticker = m.group(1)
        if ":" in ticker:
            continue
        if ticker in index and index[ticker] != url:
            ambiguous.add(ticker)
            continue
        index[ticker] = url
    for ticker in ambiguous:
        index.pop(ticker, None)
    return index


_TICKER_URL_INDEX = _build_ticker_url_index()


def resolve_gurufocus_url(ticker: str) -> Optional[str]:
    """Best-effort ticker -> GuruFocus summary URL. Returns None if the
    ticker isn't in the reverse index under either its exact form or the
    "-" -> "." normalized form (e.g. BRK-B -> BRK.B)."""
    if ticker in _TICKER_URL_INDEX:
        return _TICKER_URL_INDEX[ticker]
    return _TICKER_URL_INDEX.get(ticker.replace("-", "."))


def _parse_soup(symbol: str, url: str, soup) -> Optional[dict]:
    """Returns an Analysis-shaped dict, or None if the page couldn't be
    parsed - either because GuruFocus served a Cloudflare interstitial
    instead of the real page (common under concurrent fetches - a fresh
    browser context on retry usually clears it) or because price/GF Value
    genuinely aren't on the page."""
    try:
        gf = extract_stock_info(soup)
    except Exception as e:
        LOGGER.error(f"Error parsing {symbol} ({url}): {e}")
        return None
    if gf is None:
        return None
    analysis = to_valuation_analysis(symbol, gf)
    if analysis is None:
        return None
    return analysis.dict()


def analyze_via_gurufocus(symbols: List[str], concurrency: int = 3) -> Dict[str, dict]:
    """Fetch and parse valuation data for `symbols` from GuruFocus.

    Returns {symbol: Analysis-shaped dict} for every symbol that resolved to
    a URL and parsed successfully. Unresolvable or unparseable symbols are
    skipped and logged rather than raising, matching how the Alphaspread
    fetcher used to swallow per-ticker failures. A single retry pass (with a
    fresh browser context, via a new scrape_urls_async call) is made for
    anything that failed to fetch or parse the first time - GuruFocus's
    Cloudflare challenge is more likely to trip on many concurrent page loads
    sharing one browser context than on an isolated retry.
    """
    url_to_symbol: Dict[str, str] = {}
    for symbol in symbols:
        url = resolve_gurufocus_url(symbol)
        if url is None:
            LOGGER.warning(f"No GuruFocus URL found for {symbol!r}, skipping")
            continue
        url_to_symbol[url] = symbol

    urls = list(url_to_symbol.keys())
    LOGGER.info(f"Resolved {len(urls)}/{len(symbols)} symbols to GuruFocus URLs")
    if not urls:
        return {}

    soups = scrape_urls_async(urls, concurrency=concurrency)

    results: Dict[str, dict] = {}
    failed_urls: List[str] = []
    for url in urls:
        symbol = url_to_symbol[url]
        soup = soups.get(url)
        analysis = _parse_soup(symbol, url, soup) if soup is not None else None
        if analysis is None:
            failed_urls.append(url)
        else:
            results[symbol] = analysis

    if failed_urls:
        LOGGER.info(f"Retrying {len(failed_urls)} URLs that failed to fetch or parse on the first pass")
        retry_soups = scrape_urls_async(failed_urls, concurrency=concurrency)
        still_failed = []
        for url in failed_urls:
            symbol = url_to_symbol[url]
            soup = retry_soups.get(url)
            analysis = _parse_soup(symbol, url, soup) if soup is not None else None
            if analysis is None:
                still_failed.append(symbol)
            else:
                results[symbol] = analysis
        if still_failed:
            LOGGER.warning(f"Failed to fetch/parse {len(still_failed)} symbols even after retry: {still_failed}")

    LOGGER.info(f"Successfully analyzed {len(results)}/{len(symbols)} symbols via GuruFocus")
    return results
