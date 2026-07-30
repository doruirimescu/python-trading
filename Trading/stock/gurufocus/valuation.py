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
import time
from typing import Dict, List, Optional

from Trading.symbols.constants import GURUFOCUS_STOCK_SYMBOLS_DICT
from Trading.stock.gurufocus.gurufocus import extract_stock_info, to_valuation_analysis
from Trading.utils.custom_logging import get_logger
from Trading.utils.html_utils import scrape_urls_async

LOGGER = get_logger("gurufocus_valuation")

# Firing all ~500 tickers through one big concurrent batch (even at
# concurrency=3) sustains several requests/second continuously, which trips
# GuruFocus's rate-based Cloudflare protection: a real run measured 5/503
# succeeding before every subsequent request - both on the first pass and an
# immediate retry - got a challenge page instead of real content. Pacing
# requests into small chunks with a real delay between them, and a longer
# cooldown before retrying failures, keeps the sustained rate low enough to
# stay under whatever threshold is tripping that block. This isn't
# latency-sensitive (a daily batch job), so trading speed for reliability
# here is the right call.
_CHUNK_SIZE = 5
_CHUNK_DELAY_SECONDS = 5.0
_RETRY_COOLDOWN_SECONDS = 60.0

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


def _fetch_paced(urls: List[str], concurrency: int) -> Dict[str, object]:
    """Fetch `urls` in small chunks with a delay between chunks, instead of
    one big concurrent batch, to keep the sustained request rate low."""
    soups: Dict[str, object] = {}
    for i in range(0, len(urls), _CHUNK_SIZE):
        chunk = urls[i : i + _CHUNK_SIZE]
        soups.update(scrape_urls_async(chunk, concurrency=concurrency))
        if i + _CHUNK_SIZE < len(urls):
            time.sleep(_CHUNK_DELAY_SECONDS)
    return soups


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


def analyze_via_gurufocus(symbols: List[str], concurrency: int = 2) -> Dict[str, dict]:
    """Fetch and parse valuation data for `symbols` from GuruFocus.

    Returns {symbol: Analysis-shaped dict} for every symbol that resolved to
    a URL and parsed successfully. Unresolvable or unparseable symbols are
    skipped and logged rather than raising, matching how the Alphaspread
    fetcher used to swallow per-ticker failures. A single retry pass, after a
    cooldown, is made for anything that failed to fetch or parse the first
    time.
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

    soups = _fetch_paced(urls, concurrency)

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
        LOGGER.info(
            f"{len(failed_urls)} URLs failed to fetch or parse on the first pass; "
            f"cooling down {_RETRY_COOLDOWN_SECONDS:.0f}s before retrying, in case the "
            "first pass tripped a rate limit"
        )
        time.sleep(_RETRY_COOLDOWN_SECONDS)
        retry_soups = _fetch_paced(failed_urls, concurrency)
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
