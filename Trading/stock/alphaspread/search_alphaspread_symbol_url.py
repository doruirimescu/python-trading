# pip install ddgs
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse


def _extract_alphaspread_symbol(href: str) -> Optional[str]:
    """
    Extract the ticker symbol from an AlphaSpread URL.

    Expected form:
      https://www.alphaspread.com/public/stock/<EXCHANGE>/<SYMBOL>/summary
    """
    try:
        print("Extracting symbol from URL:", href)
        parsed = urlparse(href)
        segments = [s for s in (parsed.path or "").split("/") if s]

        # Remove trailing 'summary'
        if segments and segments[-1].lower() == "summary":
            return segments[-2]
        if not segments:
            return None
    except Exception:
        return None


def search_alphaspread_symbol_url(
    query: str,
    *,
    region: str = "wt-wt",
    safesearch: str = "strict",  # "off" | "moderate" | "strict"
    timelimit: Optional[str] = None  # "d", "w", "m", "y"
) -> Optional[Tuple[str, str]]:
    """
    Return (symbol, url) for the first AlphaSpread result whose path ends with 'summary'.
    If a hit ends with 'financials', rewrite it to 'summary' and return that instead.
    If not found or symbol can't be parsed, return None.
    """
    try:
        from ddgs import DDGS  # type: ignore

        with DDGS() as ddgs:
            gen = ddgs.text(
                query,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                max_results=25,
            )
            for item in gen:
                href = (item or {}).get("href")
                if not href:
                    continue

                try:
                    parsed = urlparse(href)
                    host_ok = "alphaspread" in (parsed.netloc or "").lower()
                    if not host_ok:
                        continue

                    path = parsed.path or ""
                    path_clean = path.rstrip("/")

                    # Accept either /summary or /financials; if financials, rewrite to summary
                    if path_clean.endswith("summary"):
                        target_url = href
                    elif path_clean.endswith("financials"):
                        new_path = path_clean[: -len("financials")] + "summary"
                        # Preserve query/fragment, only change path
                        parsed_new = parsed._replace(path=new_path)
                        target_url = urlunparse(parsed_new)
                    else:
                        continue

                    symbol = _extract_alphaspread_symbol(target_url)
                    if symbol:
                        return symbol, target_url
                except Exception:
                    continue
            return None
    except Exception:
        return None


# Example:
if __name__ == "__main__":
    result = search_alphaspread_symbol_url(
        "alphaspread zim integrated shipping services summary"
    )
    if result:
        symbol, url = result
        print(symbol, "-", url)
    else:
        print("No result found.")
