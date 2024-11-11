import re
from enum import Enum
from typing import Tuple, Optional

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel


import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

def scroll_down(driver):
    """Scroll down the webpage using ActionChains."""
    actions = ActionChains(driver)
    body = driver.find_element(By.TAG_NAME, 'body')
    body.click()
    actions.send_keys(Keys.PAGE_DOWN).perform()
    actions.send_keys(Keys.PAGE_DOWN).perform()

    time.sleep(0.5)
    actions.send_keys(Keys.PAGE_DOWN).perform()
    actions.send_keys(Keys.PAGE_DOWN).perform()
    time.sleep(0.5)


def get_piotroski_f_score(driver, url):
    driver.get(url)
    try:
        # Wait for the table containing the Piotroski F-Score to load
        scroll_down(driver)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.relative-box.children-card"))
        )

        last_breadcrumb = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Breadcrumb']//span[@class='el-breadcrumb__item'][last()]//span[@class='el-breadcrumb__inner']")))
        name = last_breadcrumb.text.strip()
        # Locate the table row containing the Piotroski F-Score and get the corresponding score
        score_element = driver.find_element(By.XPATH, "//div[@class='relative-box children-card']//table//tr[1]//td[@class='t-right t-primary']")
        f_score = score_element.text.strip()

        # Wait for the GF Score element and retrieve it
        gfscore_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@id, 'gf-score-section-')]//span[@class='t-primary']"))
        )
        gf_score = gfscore_element.text.strip()

        return name, f_score, gf_score

    except Exception as e:
        print(f"Error: {e}")
    return None

# # Initialize the WebDriver
# driver = webdriver.Chrome()

# # URL to scrape
# url = "https://www.gurufocus.com/stock/CHIX:VITBS/summary"

# # Get the Piotroski F-Score
# f_score, g_score = get_piotroski_f_score(driver, url)
# if f_score:
#     print(f"Piotroski F-score: {f_score} found. GF score: {g_score}")
