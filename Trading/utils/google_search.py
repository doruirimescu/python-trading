from googlesearch import search

class GoogleSearchFailed(Exception):
    def __init__(self, query):
        super().__init__(f"Google search failed. Query: {query}")

def get_first_google_result(query):
    try:
        search_results = search(query, num_results=1)
        first_result = next(search_results)
        return first_result
    except StopIteration:
        raise GoogleSearchFailed(query)
