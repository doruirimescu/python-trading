from playwright.sync_api import sync_playwright

def scrape_gurufocus_dynamic(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)

        # Wait for dynamic content
        page.wait_for_selector('div.stock-summary-valuation-txt span', timeout=60000)

        data = {}

        # GuruFocus Value Tag
        gf_value_tag = page.query_selector("div.stock-summary-valuation-txt span")
        data['gurufocus_value_tag'] = gf_value_tag.inner_text().replace('●', '').strip() if gf_value_tag else 'Not found'

        # Financial Strength
        financial_strength = page.query_selector("a[href*='rank_balancesheet'] span")
        data['financial_strength'] = financial_strength.inner_text().strip() if financial_strength else 'Not found'

        # Piotroski F-Score
        piotroski_f_score = page.query_selector("a[href*='term=piotroski'] span")
        data['piotroski_f_score'] = piotroski_f_score.inner_text().strip() if piotroski_f_score else 'Not found'

        browser.close()
        return data

# Usage example:
url = "https://www.gurufocus.com/stock/GOGL/summary"
result = scrape_gurufocus_dynamic(url)
print(result)
