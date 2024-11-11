#!/usr/bin/env python3

from Trading.stock.gurufocus.gurufocus import get_piotroski_f_score
from Trading.utils.google_search import get_first_google_result
from Trading.utils.cli import Named
from Trading.utils.custom_logging import get_logger
import fire
from selenium import webdriver
import time

LOGGER = get_logger(__file__)


# DEBUG=true cli.py analyze --names '["pdco", "paypal", "johnson&johnson", "mcdonalds", "pepsi", "uniper", "palantir"]'
class GuruFocusCLI(Named):
    def analyze(self):
        if not self.name and not self.names:
            LOGGER.error("Name is required")
        urls = []
        if self.name:
            urls.append(get_first_google_result("gurufocus summary " + self.name))
        if self.names:
            for name in self.names:
                LOGGER.debug(f"Searching for: {name}")
                urls.append(get_first_google_result("gurufocus summary " + name))

        LOGGER.debug(f"URLs: {urls}")

        driver = webdriver.Chrome()
        for url in urls:
            LOGGER.info(f"Scraping {url}")
            name, f_score, g_score = get_piotroski_f_score(driver, url)
            LOGGER.info(f"{name} " f"Piotroski F-score: {f_score}. GF score: {g_score}")

            time.sleep(0.5)
        driver.quit()

if __name__ == "__main__":
    fire.Fire(GuruFocusCLI)
