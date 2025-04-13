from typing import Optional, List
from Trading.utils.custom_logging import get_logger
from stateful_data_processor.file_rw import JsonFileRW

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

class JsonFileWriter(object):
    def __init__(self, filename: Optional[str] = None):
        if filename is None:
            return
        self.filename = filename
        LOGGER.debug(f"Filename: {filename}")
        self.json_file_writer = JsonFileRW(filename)
