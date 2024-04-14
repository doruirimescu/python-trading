from googlesearch import search
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger(__name__)
class GoogleSearchFailed(Exception):
    def __init__(self, query: str):
        message = f"Google search failed. Query: {query}"
        LOGGER.error(message)
        super().__init__(message)

def get_first_google_result(query: str) -> str:
    """Google search for query and return the first result

    Args:
        query (str): The query to search for

    Raises:
        GoogleSearchFailed: If the search fails

    Returns:
        str: The first result of the search
    """
    try:
        search_results = search(query, num_results=1)
        first_result = next(search_results)
        return first_result
    except StopIteration:
        raise GoogleSearchFailed(query)
