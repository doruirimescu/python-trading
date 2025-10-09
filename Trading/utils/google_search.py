from Trading.utils.custom_logging import get_logger
from Trading.config.config import GURUFOCUS_DOWNLOADS_PATH, GOOGLE_API_KEY, GOOGLE_CX
import requests

LOGGER = get_logger(__file__)
class GoogleSearchFailed(Exception):
    def __init__(self, query: str):
        message = f"Google search failed. Query: {query}"
        LOGGER.error(message)
        super().__init__(message)

def get_first_google_result_auth(query: str, api_key: str, cx: str, gl: str = "us", hl: str = "en"):
    params = {"key": api_key, "cx": cx, "q": query, "num": 1, "gl": gl, "hl": hl}
    r = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=15)
    r.raise_for_status()
    items = r.json().get("items", [])
    try:
        return next((it.get("link") for it in items if it.get("link")), None)
    except StopIteration:
        raise GoogleSearchFailed(query)

# def get_first_google_result(query, gl="us", hl="en"):
#     return get_first_google_result_auth(query, GOOGLE_API_KEY, GOOGLE_CX, gl, hl)


def get_first_google_result(query: str, sleep_interval_s: float = 0) -> str:
    """Google search for query and return the first result

    Args:
        query (str): The query to search for

    Raises:
        GoogleSearchFailed: If the search fails

    Returns:
        str: The first result of the search
    """
    try:
        from googlesearch import search
        search_results = search(query, num_results=1, sleep_interval=sleep_interval_s)
        print("Search results:", list(search_results))
        first_result = next(search_results)
        return first_result
    except StopIteration:
        raise GoogleSearchFailed(query)
    except Exception as e:
        raise GoogleSearchFailed(query)

class SearchResult:
    def __init__(self, url, title, description):
        self.url = url
        self.title = title
        self.description = description

    def __repr__(self):
        return f"SearchResult(url={self.url}, title={self.title}, description={self.description})"


import asyncio
import aiohttp
from typing import Iterable, List, Optional

# If this already exists in your codebase, you can remove this definition.
class GoogleSearchFailed(Exception):
    pass


_GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


async def _fetch_first_result(
    session: aiohttp.ClientSession,
    query: str,
    api_key: str,
    cx: str,
    gl: str,
    hl: str,
    timeout: float,
    semaphore: asyncio.Semaphore,
) -> Optional[str]:
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 1,
        "gl": gl,
        "hl": hl,
    }
    async with semaphore:
        try:
            async with session.get(_GOOGLE_SEARCH_URL, params=params, timeout=timeout) as resp:
                resp.raise_for_status()
                data = await resp.json()
                items = data.get("items", []) or []
                # Return the first valid link if present
                for it in items:
                    link = it.get("link")
                    if link:
                        return link
                return None
        except aiohttp.ClientResponseError as e:
            # Treat per-query failures as None (like your single helper returning None)
            # Raise GoogleSearchFailed if you prefer to hard-fail:
            # raise GoogleSearchFailed(f"{query}: {e.status} {e.message}") from e
            return None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None


async def get_first_google_result_auth_batch(
    queries: Iterable[str],
    api_key: str,
    cx: str,
    gl: str = "us",
    hl: str = "en",
    *,
    timeout: float = 15.0,
    concurrency: int = 10,
) -> List[Optional[str]]:
    """
    Fetch the first Google result for each query in parallel.

    Returns a list of links (or None) in the same order as `queries`.
    """
    queries = list(queries)
    semaphore = asyncio.Semaphore(concurrency)

    connector = aiohttp.TCPConnector(limit=0)  # unlimited connections; we gate via semaphore
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            _fetch_first_result(session, q, api_key, cx, gl, hl, timeout, semaphore)
            for q in queries
        ]
        # Gather ensures results maintain the same order as tasks/queries
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)


# Convenience wrapper that mirrors your non-auth helper and uses your globals.
# Usage: await get_first_google_result_batch(["foo", "bar"])
async def get_first_google_result_batch(
    queries: Iterable[str],
    gl: str = "us",
    hl: str = "en",
    *,
    timeout: float = 15.0,
    concurrency: int = 10,
) -> List[Optional[str]]:
    return await get_first_google_result_auth_batch(
        queries,
        GOOGLE_API_KEY,
        GOOGLE_CX,
        gl=gl,
        hl=hl,
        timeout=timeout,
        concurrency=concurrency,
    )


# --- Optional sync helper (callable outside of an event loop) ---
def get_first_google_result_batch_sync(
    queries: Iterable[str],
    gl: str = "us",
    hl: str = "en",
    *,
    timeout: float = 15.0,
    concurrency: int = 10,
) -> List[Optional[str]]:
    """
    Synchronous convenience wrapper. If you're already in an async context,
    call `await get_first_google_result_batch(...)` instead.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If already in an event loop, user should call the async API.
        # Fall back to creating a task group and running it via loop.
        # (This will work in environments like Jupyter that already have a loop.)
        return loop.run_until_complete(  # type: ignore[attr-defined]
            get_first_google_result_batch(
                queries, gl=gl, hl=hl, timeout=timeout, concurrency=concurrency
            )
        )
    else:
        return asyncio.run(
            get_first_google_result_batch(
                queries, gl=gl, hl=hl, timeout=timeout, concurrency=concurrency
            )
        )

class GoogleSearcher:
    def __init__(self, sleep_interval_s: float = 0) -> None:
        self.n_searches = 0
        self.current_user_agent_index = 0
        self.sleep_interval_s = sleep_interval_s

    def __increment_user_agent_index(self):
        self.current_user_agent_index += 1
        if self.current_user_agent_index >= len(user_agent_list):
            self.current_user_agent_index = 0

    def __get_current_user_agent(self):
        if self.n_searches % 3 == 0:
            self.__increment_user_agent_index()
        return user_agent_list[self.current_user_agent_index]

    def get_first_google_result(self, query: str) -> str:
        self.n_searches += 1
        try:
            ua = self.__get_current_user_agent()
            search_results = search(query, num_results=1, sleep_interval=self.sleep_interval_s,
                                    user_agent=ua)
            return search_results
        except StopIteration:
            raise GoogleSearchFailed(query)
        except requests.exceptions.HTTPError as e:
            self.__increment_user_agent_index()
            LOGGER.error(e)

            if self.current_user_agent_index == 0:
                raise GoogleSearchFailed(query)
            return self.get_first_google_result(query)

        except Exception as e:
            LOGGER.error(e)
            raise GoogleSearchFailed(query)
        return ""

if __name__ == "__main__":
    print(get_first_google_result("alpha spread apple"))
    print(get_first_google_result("yahoo finance apple"))
