from typing import Optional, List
from Trading.utils.custom_logging import get_logger

LOGGER = get_logger(__file__)

class Named(object):
    def __init__(self, name: Optional[str] = None, names: Optional[List[str]] = None):
        self.name = name
        self.names = names
        LOGGER.debug(f"Name: {name}, Names: {names}")

# create a filter class that allows for filtering by given parameter-value pairs
class Filter(object):
    def __init__(self, filters: Optional[dict] = None):
        self.filters = filters if filters else {}
        LOGGER.debug(f"Filters: {filters}")
