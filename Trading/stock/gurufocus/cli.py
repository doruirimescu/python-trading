#!/usr/bin/env python3

from Trading.stock.gurufocus.gurufocus import GurufocusAnalyzer
from Trading.utils.google_search import get_first_google_result
from Trading.utils.cli import Named, JsonFileWriter
from Trading.utils.custom_logging import get_logger
from Trading.config.config import GURUFOCUS_DOWNLOADS_PATH
from typing import Optional, List
import fire
from Trading.utils.time import get_datetime_now_cet
from Trading.utils.html import scrape_urls_async

LOGGER = get_logger(__file__)


# DEBUG=true cli.py analyze --names '["pdco", "paypal", "johnson&johnson", "mcdonalds", "pepsi", "uniper", "palantir"]'
class GuruFocusCLI(Named, JsonFileWriter):
    def __init__(
        self,
        name: Optional[str] = None,
        names: Optional[List[str]] = None,
        filename: Optional[str] = None,
    ):
        Named.__init__(self, name=name, names=names)
        if filename is None:
            filename = GURUFOCUS_DOWNLOADS_PATH / f"{str(get_datetime_now_cet())}gurufocus.json"
        JsonFileWriter.__init__(self, filename=filename)

    def analyze(self):
        if not self.name and not self.names:
            LOGGER.error("Name is required")
        urls = []
        if self.name:
            urls.append(get_first_google_result("gurufocus summary " + self.name))
        if self.names:
            for name in self.names:
                urls.append(get_first_google_result("gurufocus summary " + name))
        LOGGER.debug(f"URLs: {urls}")

        gf_analyzer = GurufocusAnalyzer(self.json_file_writer)
        urls_soups = scrape_urls_async(urls)
        gf_analyzer.run(items=urls_soups.values(), data={})


if __name__ == "__main__":
    fire.Fire(GuruFocusCLI)

# DEBUG=true python3 cli.py analyze --names '["pdco", "paypal", "johnson&johnson", "mcdonalds", "pepsi", "uniper", "palantir", "amd", "nvidia", "apple", "microsoft", "google", "amazon", "meta", "tesla", "on semiconductor", "asml", "qualcomm", "broadcom", "marvell", "infineon", "nokia", "ericsson", "siemens", "philips", "schneider electric", "abb", "general electric", "honeywell", "rockwell automation"]'
