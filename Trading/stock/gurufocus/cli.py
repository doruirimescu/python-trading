#!/usr/bin/env python3

from Trading.stock.gurufocus.gurufocus import download_html, extract_stock_info
from Trading.utils.google_search import get_first_google_result
from Trading.utils.cli import Named
from Trading.utils.custom_logging import get_logger
from typing import Optional, List
import os
import fire
import time

LOGGER = get_logger(__file__)


# DEBUG=true cli.py analyze --names '["pdco", "paypal", "johnson&johnson", "mcdonalds", "pepsi", "uniper", "palantir"]'
class GuruFocusCLI(Named):
    def __init__(self, name: Optional[str] = None, names: Optional[List[str]] = None):
        Named.__init__(self, name=name, names=names)
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

        for url in urls:
            LOGGER.info(f"Scraping {url}")
            download_html(url, filename="gurufocus_page.html")
            html_file_path = "gurufocus_page.html"
            stock_info = extract_stock_info(html_file_path)
            if os.path.exists(html_file_path):
                os.remove(html_file_path)
            if not stock_info:
                LOGGER.error(f"Failed to extract stock info from {url}")
                continue
            LOGGER.info(stock_info)
            time.sleep(0.5)

if __name__ == "__main__":
    fire.Fire(GuruFocusCLI)
