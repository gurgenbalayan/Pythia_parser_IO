import re
from typing import List, Optional, Dict

from selenium.webdriver import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from utils.logger import setup_logger
import os
from bs4 import BeautifulSoup
from selenium import webdriver


SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL")
STATE = os.getenv("STATE")
logger = setup_logger("scraper")
async def fetch_company_details(url: str) -> dict:
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get("https://sos.iowa.gov/search/business/search.aspx")
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        radio_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#searchBiz"))
        )
        radio_btn.click()
        first_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Number"]'))
        )
        first_input.send_keys(url)
        first_input.send_keys(Keys.RETURN)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "mainArticle"))
        )
        try:
            article = driver.find_element(By.ID, "mainArticle")
            summary_html = article.get_attribute("outerHTML")
        except Exception:
            summary_html = None
        officers = driver.find_elements(By.CSS_SELECTOR, 'a[title="Officers"]')
        if officers:
            officers[0].click()
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "mainArticle"))
            )
            article = driver.find_element(By.ID, "mainArticle")
            officers_html = article.get_attribute("outerHTML")
        else:
            officers_html = None
        filings = driver.find_elements(By.CSS_SELECTOR, 'a[title="Filings"]')
        # if filings:
        #     filings[0].click()
        #     WebDriverWait(driver, 10).until(
        #         lambda d: d.execute_script("return document.readyState") == "complete"
        #     )
        #     WebDriverWait(driver, 10).until(
        #         EC.presence_of_element_located((By.ID, "mainArticle"))
        #     )
        #     article = driver.find_element(By.ID, "mainArticle")
        #     filings_html = article.get_attribute("outerHTML")
        # else:
        #     filings_html = None
        return await parse_html_details(summary_html, officers_html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{url}': {e}")
        return {}
    finally:
        if driver:
            driver.quit()

async def fetch_company_data(query: str) -> list[dict]:
    driver = None
    url = "https://sos.iowa.gov/search/business/search.aspx"
    try:

        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        first_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#txtName"))
        )
        first_input.send_keys(query)
        first_input.send_keys(Keys.RETURN)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
                                                "#mainArticle")))
        html = driver.page_source
        return await parse_html_search(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{query}': {e}")
        return []
    finally:
        if driver:
            driver.quit()


async def parse_html_search(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.find('article', {'id': 'mainArticle'})

    count_tag = article.find('p', class_='results-count')
    if not count_tag or 'Results 0' in count_tag.get_text(strip=True).replace('\xa0', ' '):
        return []

    table = article.find('table', class_='table')
    if not table:
        return []

    rows = table.find_all('tr')[1:]
    results = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) != 4:
            continue
        business_number = cols[0].get_text(strip=True)
        results.append({
            "state": STATE,
            'id': business_number,
            'name': cols[1].get_text(strip=True),
            'status': cols[2].get_text(strip=True),
            'url': business_number,
        })
    return results

async def parse_html_details(summary_html: str, officers_html: str) -> dict:

    result = {}
    result["state"] = STATE
    soup = BeautifulSoup(summary_html, "html.parser")
    article = soup.find("article", id="mainArticle")
    if summary_html:
        tables = article.find_all("table")

        # Business summary table
        summary = tables[0].find_all("tr")
        result["registration_number"] = summary[1].find_all("td")[0].text.strip()
        result["name"] = summary[1].find_all("td")[1].text.strip()
        result["status"] = summary[1].find_all("td")[2].text.strip()

        result["entity_type"] = summary[3].find_all("td")[0].text.strip()

        if summary[5].find_all("td")[0].text.strip() == "PERPETUAL":
            result["expiration_date"] = None
        else:
            result["expiration_date"] = summary[5].find_all("td")[0].text.strip()

        result["date_registered"] = summary[5].find_all("td")[1].text.strip()


        # Agent Info
        agent_table = tables[2].find_all("tr")
        result["agent_name"] = agent_table[1].text.strip()
        result["agent_address"] = agent_table[3].find_all("td")[0].text.strip() + ", " + agent_table[5].text.strip()

        # Home Office
        home_office_table = tables[3].find_all("tr")
        result["prinicipal_address"] = home_office_table[3].find_all("td")[0].text.strip() + ", " + home_office_table[5].text.strip()

    soup = BeautifulSoup(officers_html, "html.parser")
    article = soup.find("article", id="mainArticle")
    if officers_html and "None on file" not in officers_html:
        rows = article.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 6:
                type_ = cols[0].text.strip()
                name = cols[1].text.strip()
                street = cols[2].text.strip()
                city = cols[3].text.strip()
                state = cols[4].text.strip()
                zip_code = cols[5].text.strip()
                address = f"{street}, {city}, {state} {zip_code}"
                result["officers"].append({
                    "title": type_,
                    "name": name,
                    "address": address
                })

    # soup = BeautifulSoup(filings_html, "html.parser")
    # article = soup.find("article", id="mainArticle")
    documents = []
    # if filings_html and "None on file" not in filings_html:
    #     rows = article.find_all("tr")[1:]
    #     for row in rows:
    #         cols = row.find_all("td")
    #         if len(cols) >= 2:
    #             title = cols[4].text.strip()
    #             date = cols[2].text.strip()
    #             link = cols[0].find("a")
    #             if link and link.has_attr("href"):
    #                 url = link["href"]
    #                 documents.append({
    #                     "name": title,
    #                     "date": date,
    #                     "url": "https://sos.iowa.gov/search/business/" + url
    #                 })
    result["documents"] = documents

    return result