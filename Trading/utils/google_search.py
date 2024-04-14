from googlesearch import search
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger(__name__)
class GoogleSearchFailed(Exception):
    def __init__(self, query):
        message = f"Google search failed. Query: {query}"
        LOGGER.error(message)
        super().__init__(message)

def get_first_google_result(query):
    try:
        search_results = search(query, num_results=1)
        first_result = next(search_results)
        return first_result
    except StopIteration:
        raise GoogleSearchFailed(query)
