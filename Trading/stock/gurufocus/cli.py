#!/usr/bin/env python3

from Trading.stock.gurufocus.gurufocus import GurufocusAnalyzer
from Trading.utils.google_search import (
    get_first_google_result,
    get_first_google_result_batch_sync,
)
from Trading.utils.cli import Named, JsonFileWriter
from Trading.utils.custom_logging import get_logger
from Trading.config.config import GURUFOCUS_DOWNLOADS_PATH
from typing import Optional, List
import fire
from Trading.utils.time import get_datetime_now_cet
from Trading.utils.html_utils import scrape_urls_async, download_rendered_html

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
            filename = (
                GURUFOCUS_DOWNLOADS_PATH
                / f"{str(get_datetime_now_cet())}gurufocus.json"
            )
        JsonFileWriter.__init__(self, filename=filename)

    def analyze(self):
        if not self.name and not self.names:
            LOGGER.error("Name is required")

        queries = ["gurufocus summary " + n for n in self.names or [self.name]]
        LOGGER.debug("Queries to scrape: " + str(queries))

        urls = get_first_google_result_batch_sync(
            ["gurufocus summary " + n for n in self.names or [self.name]],
            concurrency=10,
        )
        if all(u is None for u in urls):
            LOGGER.error("No valid URLs found from Google")
            return
        LOGGER.debug(f"URLs: {urls}")

        gf_analyzer = GurufocusAnalyzer(self.json_file_writer)

        urls_soups = scrape_urls_async(urls)
        gf_analyzer.run(items=urls_soups.values(), data={})
        download_rendered_html(urls[0], filename=self.names[0]+"_test.html")
        download_rendered_html(urls[-1], filename=self.names[-1]+"test.html")


if __name__ == "__main__":
    fire.Fire(GuruFocusCLI)

# DEBUG=true python3 cli.py analyze --names '["pdco", "paypal", "johnson&johnson", "mcdonalds", "pepsi", "uniper"]'
