from googlesearch import search


def get_first_google_result(query):
    try:
        search_results = search(query, num_results=1)
        first_result = next(search_results)
        return first_result
    except StopIteration:
        return None
