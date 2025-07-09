# File: scrape_final_robust_fixed.py

import pandas as pd
from pandas import DataFrame
import time
from typing import Literal
from datetime import datetime 

from detonator import get_logger, df_2_mongo
from dataminer.models import MarketPe
from dataminer import TradeCalendarShovel

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

_logger = get_logger("MarketValuationScraper")
_tcs = TradeCalendarShovel.get_instance()

class MarketValuationScraper:
    NASDAT_100_PE_RATIO_URL = "https://www.gurufocus.com/economic_indicators/6778/nasdaq-100-pe-ratio"
    SP500_PE_RATIO_URL = "https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio"

    def __init__(self):
        pass

    def handle_popups(self, driver, wait):
        """
        Checks for and closes the login/subscription pop-up dialog.
        This function is non-blocking and will not fail if the pop-up is not present.
        """
        try:
            # This is the specific locator for the pop-up's close button
            dialog_close_locator = (
                By.CSS_SELECTOR, 'div.el-dialog__wrapper button.el-dialog__headerbtn')
            # Use a short wait time to quickly check for the pop-up
            short_wait = WebDriverWait(driver, 2)
            close_button = short_wait.until(
                EC.element_to_be_clickable(dialog_close_locator))
            _logger.info(
                "Login/subscription pop-up found. Attempting to close it.")
            close_button.click()
            time.sleep(1)  # Give a moment for the dialog to disappear
        except TimeoutException:
            # This is expected if the pop-up is not present. Do nothing.
            _logger.info("No pop-up dialog found. Continuing...")
        except Exception as e:
            _logger.warning(
                f"An error occurred while trying to close the pop-up: {e}")

    def _scrape_paginated_table_robust_final(self, idx: Literal['spx', 'qqq'] = 'spx', start_date='0000,00,00', end_date='') -> bool:
        """
        Scrapes a paginated table with robust pop-up handling and click strategies.
        """
        # target_url = "https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio"
        target_url = None
        if idx == 'spx':
            target_url = self.SP500_PE_RATIO_URL
        elif idx == 'qqq':
            target_url = self.NASDAT_100_PE_RATIO_URL
        else:
            raise ValueError("Invalid index type. Use 'spx' or 'qqq'.")

        table_locator = (By.ID, "non-sticky-table")
        next_button_locator = (By.CSS_SELECTOR, "button.btn-next")
        # This locator will be used to detect when a page is loading new data
        loading_mask_locator = (By.CSS_SELECTOR, "div.el-loading-mask")

        options = webdriver.ChromeOptions()
        # Running in headed mode is often more stable for complex sites like this
        # options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        driver = None
        try:
            _logger.info("Initializing WebDriver...")
            service = ChromeService(ChromeDriverManager().install())
            _logger.info("Attempting to open Chrome now...")
            driver = webdriver.Chrome(service=service, options=options)
            _logger.info("WebDriver initialized successfully.")

            wait = WebDriverWait(driver, 20)  # A reasonable default wait time

            _logger.info("Navigating to URL: %s", target_url)
            driver.get(target_url)

            # Initial check for any pop-ups on page load
            self.handle_popups(driver, wait)

            _logger.info("Waiting for the data table to become visible...")
            table_element = wait.until(
                EC.visibility_of_element_located(table_locator))

            header_elements = table_element.find_elements(
                By.XPATH, ".//thead//th")
            header = [h.text.strip()
                      for h in header_elements if h.text.strip()]
            _logger.info("Scraped table header: %s", header)

            page_number = 1
            go = True

            while go:
                _logger.info("Starting scrape for page %d.", page_number)

                all_rows_data = []
                # This ensures the data on the page is stable and not from the previous page.
                wait.until(EC.invisibility_of_element_located(
                    loading_mask_locator))

                # Wait for at least one row to be present in the table body
                wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="non-sticky-table"]//tbody/tr')))
                table_rows = driver.find_elements(
                    By.XPATH, '//*[@id="non-sticky-table"]//tbody/tr')
                _logger.info("Found %d rows on page %d.",
                             len(table_rows), page_number)

                for row in table_rows:
                    row_data = [cell.text for cell in row.find_elements(
                        By.TAG_NAME, "td")]
                    if len(row_data) == len(header):
                        all_rows_data.append(row_data)
                    else:
                        _logger.warning("Row data length (%d) doesn't match header length (%d). Skipping row: %s", len(
                            row_data), len(header), row_data)
                go = self._to_db(idx=idx, df=pd.DataFrame(all_rows_data, columns=header), start_date=start_date, end_date=end_date)

                try:
                    # Before interacting with the 'Next' button, check for and close any pop-ups.
                    self.handle_popups(driver, wait)

                    next_button = driver.find_element(*next_button_locator)
                    _logger.debug(next_button.get_attribute('disabled'))
                    if next_button.get_attribute("disabled") == "true":
                        _logger.info(
                            "Last page reached (Next button is disabled).")
                        break

                    _logger.info("Scrolling to and clicking 'Next' button...")

                    # --- FIX 3 (Part 2): USE A JAVASCRIPT CLICK FOR ROBUSTNESS ---
                    # This is less likely to be intercepted than a standard Selenium click.
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(0.5)  # A brief pause can help stability
                    driver.execute_script("arguments[0].click();", next_button)

                    page_number += 1

                except NoSuchElementException:
                    _logger.info(
                        "No more 'Next' button found. Assuming end of pages.")
                    break
                except Exception as e:
                    _logger.error(
                        "An unexpected error occurred while trying to navigate to the next page: %s", e)
                    break

            return True

        except Exception as e:
            _logger.exception(
                "An unexpected error occurred during the scraping process:%s.", e)
            return False
        finally:
            if driver:
                _logger.info("Closing the browser session.")
                driver.quit()

    def _to_db(self, idx: Literal['spx', 'qqq'] = 'spx', df: DataFrame = None, start_date:str='', end_date:str='') -> bool:
        """
        Scrapes the PE ratio for a given index and saves it to the database.
        This is a private method intended for internal use.
        """
        _logger.info("Saving to database for index: %s:%s %s->%s", idx, df.shape, start_date, end_date)
        if df is None or df.empty:
            _logger.error("DataFrame is empty or None. Exiting.")
            return False
        try:
            df['idx'] = idx
            df['trade_date'] = pd.to_datetime(
                df['Date'], format='%Y-%m-%d').dt.strftime('%Y,%m,%d,%H,%M,%S,%f')
            df['yoy_change'] = df['YOY (%)'].str.replace('-', '0', regex=False).str.rstrip(
                '%').astype(float)  # Placeholder for YOY change
            df['pe'] = df['Value'].astype(float)
            df = df[['idx', 'trade_date', 'pe', 'yoy_change']]
            _logger.info("DataFrame after processing: %s", df)
            to_save = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
            _logger.info("Filtered data to save: %s", to_save)
            if to_save.empty:
                _logger.info("No data to save for the specified date range.")
                return False
            df_2_mongo(to_save, MarketPe)
            return len(to_save) == len(df)
        except Exception as e:
            _logger.error(
                "An error occurred while saving to the database: %s", exc_info=e)
            return False

    def update_idx_pe_to_db(self, idx: Literal['spx', 'qqq'] = 'spx', start_date:str='0000,00,00', end_date:str='9999,12,31') -> bool:
        """
        Scrapes the PE ratio for a given index and saves it to the database.
        """
        return self._scrape_paginated_table_robust_final(idx=idx, start_date=start_date, end_date=end_date)

    def update_idx_pe_to_latest(self, idx: Literal['spx', 'qqq'] = 'spx') -> bool:
        """
        Scrapes the latest PE ratio for a given index and saves it to the database.
        """
        latest_pe = MarketPe.objects(idx=idx).order_by('-trade_date').limit(1).first()
        if latest_pe:
            _logger.debug(latest_pe.trade_date)
            _logger.debug(type(latest_pe.trade_date))
            start_date = datetime.strptime(_tcs.us_trade_dates_since(start_date=latest_pe.trade_date)[-1], '%Y%m%d').strftime('%Y,%m,%d,%H,%M,%S,%f')
        else:
            _logger.warning("No existing PE data found for index: %s, and we will try to get all the PEs", idx)
            start_date = '0000,00,00'
        self.update_idx_pe_to_db(idx=idx, start_date=start_date, end_date='9999,12,31')
        return True
