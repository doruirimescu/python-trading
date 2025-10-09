from __future__ import annotations

from typing import Optional, Tuple, List, Iterable
from urllib.parse import urlparse, urlunparse
import contextlib


class AlphaSpreadSearcher:
    """
    Find AlphaSpread summary URLs via DuckDuckGo (ddgs).

    Usage:
        with AlphaSpreadSearcher(region="wt-wt") as s:
            one = s.search_one("Apple")
            many = s.search_many(["Tesla", "Coca-Cola", "MSFT"])
    """

    def __init__(
        self,
        *,
        region: str = "wt-wt",
        safesearch: str = "strict",  # "off" | "moderate" | "strict"
        timelimit: Optional[str] = None,  # "d", "w", "m", "y"
        max_results: int = 100,
    ) -> None:
        self.region = region
        self.safesearch = safesearch
        self.timelimit = timelimit
        self.max_results = max_results

        self._ddgs = None  # lazily created
        self._ddgs_cm = None  # context manager

    # --------------- Context management (pools the connection) ---------------

    def __enter__(self) -> "AlphaSpreadSearcher":
        self._ensure_ddgs()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_ddgs(self) -> None:
        if self._ddgs is None:
            from ddgs import DDGS  # type: ignore

            self._ddgs_cm = DDGS()
            # Use DDGS as a context manager to reuse a single client
            self._ddgs = self._ddgs_cm.__enter__()

    def close(self) -> None:
        if self._ddgs_cm is not None:
            with contextlib.suppress(Exception):
                self._ddgs_cm.__exit__(None, None, None)
        self._ddgs = None
        self._ddgs_cm = None

    # ----------------------------- Core helpers ------------------------------

    @staticmethod
    def _normalize_to_summary(href: str) -> Optional[str]:
        """
        If URL is AlphaSpread and ends with /summary (ok) or /financials (rewrite to /summary),
        return the normalized URL. Otherwise return None.
        """
        try:
            parsed = urlparse(href)
            host_ok = "alphaspread" in (parsed.netloc or "").lower()
            if not host_ok:
                return None

            path = parsed.path or ""
            path_clean = path.rstrip("/")

            if path_clean.endswith("summary"):
                return href

            if path_clean.endswith("financials"):
                new_path = path_clean[: -len("financials")] + "summary"
                parsed_new = parsed._replace(path=new_path)
                return urlunparse(parsed_new)

            return None
        except Exception:
            return None

    @staticmethod
    def _extract_alphaspread_symbol(href: str) -> Optional[str]:
        """
        Extract the ticker symbol from an AlphaSpread URL.

        Expected forms include:
          https://www.alphaspread.com/security/<EXCHANGE>/<SYMBOL>/summary
          https://www.alphaspread.com/public/stock/<EXCHANGE>/<SYMBOL>/summary
        """
        try:
            parsed = urlparse(href)
            segments = [s for s in (parsed.path or "").split("/") if s]
            if not segments:
                return None

            # Remove trailing "summary" if present
            if segments and segments[-1].lower() == "summary":
                segments = segments[:-1]

            # Expect .../<EXCHANGE>/<SYMBOL>
            if len(segments) >= 2:
                return segments[-1]  # SYMBOL
            return None
        except Exception:
            return None

    # ------------------------------- Search API ------------------------------

    def search_one(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Return (symbol, url) for the first AlphaSpread result that normalizes to a summary URL.
        If not found or symbol can't be parsed, return None.
        """
        if not query or not query.strip():
            return None

        # Ensure client is ready (supports use without context manager)
        self._ensure_ddgs()
        assert self._ddgs is not None

        try:
            gen = self._ddgs.text(
                query,
                region=self.region,
                safesearch=self.safesearch,
                timelimit=self.timelimit,
                max_results=self.max_results,
            )
            for item in gen:
                href = (item or {}).get("href")
                if not href:
                    continue

                target = self._normalize_to_summary(href)
                if not target:
                    continue

                symbol = self._extract_alphaspread_symbol(target)
                if symbol:
                    return symbol, target
            return None
        except Exception:
            return None

    def search_many(self, queries: Iterable[str]) -> List[Tuple[str, str]]:
        """
        Accepts an iterable of queries and returns a list of (symbol, url) for
        the first valid AlphaSpread result per query. Order is preserved.
        """
        results: List[Tuple[str, str]] = []
        for q in queries:
            hit = self.search_one(q)
            if hit:
                results.append(hit)
        return results


# -------------------------- Example usage -----------------------------------
# with AlphaSpreadSearcher(safesearch="strict") as s:
#     print(s.search_one("Apple"))
#     print(s.search_many(["Tesla", "Coca-Cola", "MSFT"]))
#
# # Or without context manager (it will still pool internally):
# s = AlphaSpreadSearcher()
# print(s.search_many(["NVIDIA", "Meta", "Alphabet"]))
# s.close()


def search_alphaspread_symbol_url(
    query: str,
) -> Optional[Tuple[str, str]]:
    """Wrapper around AlphaSpreadSearcher for simple use cases.
    """
    with AlphaSpreadSearcher(safesearch="strict") as s:
        return s.search_one(query)

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
