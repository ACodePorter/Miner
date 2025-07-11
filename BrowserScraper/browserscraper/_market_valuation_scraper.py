# File: scrape_final_robust_fixed.py

import pandas as pd
from pandas import DataFrame
import time
from typing import Literal
from datetime import datetime

from detonator import get_logger, df_2_mongo, make_db_connection, SingletonParent
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


class MarketValuationScraper(SingletonParent):
    NASDAT_100_PE_RATIO_URL = "https://www.gurufocus.com/economic_indicators/6778/nasdaq-100-pe-ratio"
    SP500_PE_RATIO_URL = "https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio"

    def __init__(self):
        make_db_connection()

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
            close_button.click()
            time.sleep(1)  # Give a moment for the dialog to disappear
        except TimeoutException:
            pass
        except Exception as e:
            _logger.warning(
                f"An error occurred while trying to close the pop-up: {e}")

    def _scrape_paginated_table_robust_final(self, idx: Literal['spx', 'qqq'] = 'spx', start_date='0000,00,00', end_date='') -> bool:
        """
        Scrapes a paginated table with robust pop-up handling and click strategies.
        """
        # target_url = "https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio"
        _logger.info("Starting scrape for index: %s %s -> %s",
                     idx, start_date, end_date)
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
        options.add_argument("--incognito")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        driver = None
        try:
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            wait = WebDriverWait(driver, 20)  # A reasonable default wait time
            driver.get(target_url)
            # Initial check for any pop-ups on page load
            self.handle_popups(driver, wait)
            table_element = wait.until(
                EC.visibility_of_element_located(table_locator))
            header_elements = table_element.find_elements(
                By.XPATH, ".//thead//th")
            header = [h.text.strip()
                      for h in header_elements if h.text.strip()]
            page_number = 1
            go = True

            while go:
                _logger.debug("Starting scrape for page %d.", page_number)
                all_rows_data = []
                # This ensures the data on the page is stable and not from the previous page.
                wait.until(EC.invisibility_of_element_located(
                    loading_mask_locator))
                # Wait for at least one row to be present in the table body
                wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="non-sticky-table"]//tbody/tr')))
                table_rows = driver.find_elements(
                    By.XPATH, '//*[@id="non-sticky-table"]//tbody/tr')
                for row in table_rows:
                    row_data = [cell.text for cell in row.find_elements(
                        By.TAG_NAME, "td")]
                    if len(row_data) == len(header):
                        all_rows_data.append(row_data)
                    else:
                        pass
                go = self._to_db(idx=idx, df=pd.DataFrame(
                    all_rows_data, columns=header), start_date=start_date, end_date=end_date)

                try:
                    # Before interacting with the 'Next' button, check for and close any pop-ups.
                    self.handle_popups(driver, wait)

                    next_button = driver.find_element(*next_button_locator)
                    if next_button.get_attribute("disabled") == "true":
                        break
                    # USE A JAVASCRIPT CLICK FOR ROBUSTNESS ---
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

    def _to_db(self, idx: Literal['spx', 'qqq'] = 'spx', df: DataFrame = None, start_date: str = '', end_date: str = '') -> bool:
        """
        Scrapes the PE ratio for a given index and saves it to the database.
        This is a private method intended for internal use.
        """
        _logger.info("Saving to database for index: %s:%s %s->%s",
                     idx, df.shape, start_date, end_date)
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
            to_save = df[(df['trade_date'] >= start_date)
                         & (df['trade_date'] <= end_date)]
            if to_save.empty:
                _logger.warning(
                    "No data to save for the specified date range.")
                return False
            df_2_mongo(to_save, MarketPe)
            return len(to_save) == len(df)
        except Exception as e:
            _logger.error(
                "An error occurred while saving to the database: %s", exc_info=e)
            return False

    def update_idx_pe_to_db(self, idx: Literal['spx', 'qqq'] = 'spx', start_date: str = '0000,00,00', end_date: str = '9999,12,31') -> bool:
        """
        Scrapes the PE ratio for a given index and saves it to the database.
        """
        return self._scrape_paginated_table_robust_final(idx=idx, start_date=start_date, end_date=end_date)

    def update_idx_pe_to_latest(self, idx: Literal['spx', 'qqq'] = 'spx') -> bool:
        """
        Scrapes the latest PE ratio for a given index and saves it to the database.
        """
        _logger.info("Updating latest PE for index: %s", idx)
        latest_pe = MarketPe.objects(idx=idx).order_by(
            '-trade_date').limit(1).first()
        if latest_pe:
            dates = _tcs.us_trade_dates_since(
                start_date=latest_pe.trade_date)
            if dates:
                start_date = datetime.strptime(
                    dates[-1], '%Y%m%d').strftime('%Y,%m,%d,%H,%M,%S,%f')
            else:
                _logger.info('Already up to date for index: %s @ %s',
                             idx, latest_pe.trade_date)
                return True
        else:
            _logger.info(
                "No existing PE data found for index: %s, and we will try to get all the PEs", idx)
            start_date = '0000,00,00'
        self.update_idx_pe_to_db(
            idx=idx, start_date=start_date, end_date='9999,12,31')
        return True
