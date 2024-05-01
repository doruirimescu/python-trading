from Trading.utils.custom_logging import get_logger
import requests

LOGGER = get_logger(__file__)
class GoogleSearchFailed(Exception):
    def __init__(self, query: str):
        message = f"Google search failed. Query: {query}"
        LOGGER.error(message)
        super().__init__(message)

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
        first_result = next(search_results)
        return first_result
    except StopIteration:
        raise GoogleSearchFailed(query)
    except Exception as e:
        raise GoogleSearchFailed(query)


from time import sleep
from bs4 import BeautifulSoup
from requests import get
import urllib


def _req(term, results, lang, start, proxies, timeout, user_agent):
    resp = get(
        url="https://www.google.com/search",
        headers={
            "User-Agent": user_agent
        },
        params={
            "q": term,
            "num": results + 2,  # Prevents multiple requests
            "hl": lang,
            "start": start,
        },
        proxies=proxies,
        timeout=timeout,
    )

    resp.raise_for_status()
    return resp


class SearchResult:
    def __init__(self, url, title, description):
        self.url = url
        self.title = title
        self.description = description

    def __repr__(self):
        return f"SearchResult(url={self.url}, title={self.title}, description={self.description})"


def search(term, num_results=1, lang="en", advanced=False, sleep_interval=0, timeout=5, user_agent=None):
    """Search the Google search engine"""

    escaped_term = urllib.parse.quote_plus(term)

    # Proxy
    proxies = []

    # Fetch
    start = 0
    while start < num_results:
        # Send request
        resp = _req(escaped_term, num_results - start,
                    lang, start, proxies, timeout, user_agent)
        # Parse
        soup = BeautifulSoup(resp.text, "html.parser")
        result_block = soup.find_all("div", attrs={"class": "g"})
        if result_block is None:
            LOGGER.error("No results found")
        if len(result_block) ==0:
            start += 1
        for result in result_block:
            # Find link, title, description
            link = result.find("a", href=True)
            title = result.find("h3")
            description_box = result.find(
                "div", {"style": "-webkit-line-clamp:2"})
            if description_box:
                description = description_box.text
                if link and title and description:
                    start += 1
                    if advanced:
                        return SearchResult(link["href"], title.text, description)
                    else:
                        return link["href"]
        sleep(sleep_interval)

        if start == 0:
            return []

user_agent_list = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/113.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0',

    # New additions
    'Mozilla/5.0 (iPhone; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',  # iPhone
    'Mozilla/5.0 (iPad; CPU OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1',  # iPad
    'SamsungBrowser/17.0 (Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Mobile Safari/537.36',  # Samsung Galaxy S22 Ultra
    'Dalvik/2.1.0 (Linux; U; Android 12; Pixel 6 Pro Build; SQ1D)',  # Google Pixel 6 Pro
    'DuckDuckGo/8.84.0 (Linux; android 12; Pixel 6; Build/SQ1A) like Gecko/20100101 Mobile Safari/537.36',  # DuckDuckGo app on Android 12
    'Signal/6.13.3 (Android 11; OnePlus GM1910; Build/RP1A.200720.002) Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Mobile Safari/537.36',  # Signal app on OnePlus phone
    'WhatsApp/2.24.22.13 (iPhone; iOS 17.4.1; Scale/3.00)',  # WhatsApp on iPhone
    'FaceBook/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',  # Facebook website on Windows 10
    'Twitter for Android',  # Twitter app on Android
    'Discord/200475 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Electron/19.'
]
