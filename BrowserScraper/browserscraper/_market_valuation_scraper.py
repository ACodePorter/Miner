# File: scrape_final_robust_fixed.py

import pandas as pd
from pandas import DataFrame
import time
from typing import Literal
from datetime import datetime, timedelta

from detonator import get_logger, df_2_mongo, make_db_connection, SingletonParent
from dataminer.models import MarketPe
from dataminer import TradeCalendarShovel, MarketDataShovel

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

_logger = get_logger("MarketValuationScraper")
_tcs = TradeCalendarShovel.get_instance()
_mds = MarketDataShovel.get_instance()


class MarketValuationScraper(SingletonParent):
    IDX_URL_MAP = {
        'spx': "https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio",
        'qqq': "https://www.gurufocus.com/economic_indicators/6778/nasdaq-100-pe-ratio",
        'ndx': "https://www.gurufocus.com/economic_indicators/6778/nasdaq-100-pe-ratio",
        'hsi': "https://www.gurufocus.com/economic_indicators/5732/pe-ratio-ttm-for-the-hang-seng-index"
    }

    IDX_COUNTRY_MAP = {
        'spx': ('us', 'XNYS'),
        'qqq': ('us', 'XNYS'),
        'ndx': ('us', 'XNYS'),
        'hsi': ('hk', 'XHKG')
    }

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

    def _scrape_paginated_table_robust_final(self, idx: Literal['spx', 'qqq', 'ndx', 'hsi'] = 'spx', start_date='0000,00,00', end_date='') -> bool:
        """
        Scrapes a paginated table with robust pop-up handling and click strategies.
        """
        # target_url = "https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio"
        _logger.info("Starting scrape for index: %s %s -> %s",
                     idx, start_date, end_date)
        target_url = None
        if idx not in MarketValuationScraper.IDX_URL_MAP:
            raise ValueError(
                f"Invalid index {idx}. Use {MarketValuationScraper.IDX_URL_MAP.keys()}.")
        else:
            target_url = self.IDX_URL_MAP[idx]

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

    def _to_db(self, idx: Literal['spx', 'qqq', 'ndx', 'hsi'] = 'spx', df: DataFrame = None, start_date: str = '', end_date: str = '') -> bool:
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

    def update_idx_pe_to_db(self, idx: Literal['spx', 'qqq', 'ndx', 'hsi'] = 'spx', start_date: str = '0000,00,00', end_date: str = '9999,12,31') -> bool:
        """
        Scrapes the PE ratio for a given index and saves it to the database.
        """
        return self._scrape_paginated_table_robust_final(idx=idx, start_date=start_date, end_date=end_date)

    def adj_hk_idx_pe(self, start_date: str, end_date: str) -> bool:
        """
        For each trading day, fill HSI PE using the PE of the last closed trading day before or on the 1st of the month,
        adjusted by the ratio of daily close to reference close.
        """
        _logger.info('Adjusting HSI PE from %s to %s', start_date, end_date)
        start_date = datetime.strptime(start_date, '%Y,%m,%d,%H,%M,%S,%f').strftime('%Y%m%d')
        end_date = datetime.strptime(end_date, '%Y,%m,%d,%H,%M,%S,%f').strftime('%Y%m%d')

        # 1. Get all trading days
        trade_dates = _tcs.hk_trade_dates_since(start_date=start_date, end_date=end_date)
        if not trade_dates:
            _logger.error('No HK trade dates found for %s -> %s', start_date, end_date)
            return False
        _logger.debug('Trade dates: %s', trade_dates)
        # 2. Get all HSI PE records in the range
        pe_records = MarketPe.objects(
            idx='hsi',).order_by('trade_date')  # ascending
        # 3. Get HSI daily close prices
        closest_earlier_pe = pe_records.filter(trade_date__lte=datetime.strptime(start_date, '%Y%m%d')).order_by('-trade_date').first()
        if not closest_earlier_pe:
            closest_earlier_pe = pe_records.order_by('trade_date').first()
        _logger.debug('Closest earlier PE: %s %s %s', closest_earlier_pe.trade_date, closest_earlier_pe.pe, closest_earlier_pe.idx)
        hsi_daily_df = _mds.get_ticker_daily_info('^HSI', start_date=closest_earlier_pe.trade_date - timedelta(days=15), end_date=end_date)
        if hsi_daily_df.empty:
            _logger.error('No HSI daily data found for %s -> %s', start_date, end_date)
            return False
        adjusted_pes = []
        for trade_date in trade_dates:
            _logger.debug('Trade date: %s', trade_date)
            if pe_records.filter(trade_date=datetime.strptime(trade_date, '%Y%m%d')).count() != 0:
                _logger.warning('PE record found for HSI on %s', trade_date)
                continue
            ref_pe =pe_records.filter(trade_date__lt=datetime.strptime(trade_date, '%Y%m%d')).order_by('-trade_date').first()
            if not ref_pe:
                _logger.warning('No HSI PE record found for reference on %s', trade_date)
                continue
            _logger.debug('Ref PE: %s %s %s', ref_pe.trade_date, ref_pe.pe, ref_pe.idx)
            ref_daily = hsi_daily_df[hsi_daily_df['trade_date'] <= ref_pe.trade_date.strftime('%Y,%m,%d,%H,%M,%S,%f')]
            if ref_daily.empty:
                _logger.warning('No HSI daily data found for reference on %s', trade_date)
                continue
            _logger.debug('Ref daily: %s %s %s', ref_daily.iloc[-1]['trade_date'], ref_daily.iloc[-1]['close'], ref_daily.iloc[-1]['ticker'])
            ref_close = ref_daily.iloc[-1]['close']
            daily = hsi_daily_df[hsi_daily_df['trade_date'] == datetime.strptime(trade_date, '%Y%m%d').strftime('%Y,%m,%d,%H,%M,%S,%f')]
            if daily.empty:
                _logger.warning('No HSI daily data found for %s', trade_date)
                continue
            daily_close = daily.iloc[0]['close']
            adjusted_pes.append(
                {'idx': 'hsi', 'trade_date': datetime.strptime(trade_date, '%Y%m%d').strftime('%Y,%m,%d,%H,%M,%S,%f'),
                'pe': round(ref_pe.pe * daily_close / ref_close, 2), 'yoy_change': 0})
            _logger.debug('Adjusted PE: %s %s %s', adjusted_pes[-1]['trade_date'], adjusted_pes[-1]['pe'], adjusted_pes[-1]['idx'])
        # 4. Save to DB (optional, or return as DataFrame)
        if adjusted_pes:
            df_2_mongo(pd.DataFrame(adjusted_pes), MarketPe)
            _logger.info(f"Adjusted PE for {len(adjusted_pes)} trading days.")
            return True
        else:
            _logger.warning("No adjusted PE values calculated for HSI from %s to %s", start_date, end_date)
            return False

    def update_idx_pe_to_latest(self, idx: Literal['spx', 'qqq', 'ndx', 'hsi'] = 'spx') -> bool:
        """
        Scrapes the latest PE ratio for a given index and saves it to the database.
        """
        _logger.info("Updating latest PE for index: %s", idx)
        latest_pe = MarketPe.objects(idx=idx).order_by(
            '-trade_date').limit(1).first()
        adj_start_date = None
        if latest_pe:
            c,e = self.IDX_COUNTRY_MAP[idx]
            dates = _tcs.trade_dates_since(country=c, exchange=e,
                start_date=latest_pe.trade_date)
            if dates:
                start_date = datetime.strptime(
                    dates[-1], '%Y%m%d')
                adj_start_date = (start_date - timedelta(days=1)).strftime('%Y,%m,%d,%H,%M,%S,%f')
                start_date =start_date.strftime('%Y,%m,%d,%H,%M,%S,%f')
            else:
                _logger.info('Already up to date for index: %s @ %s',
                             idx, latest_pe.trade_date)
                return True
        else:
            _logger.info(
                "No existing PE data found for index: %s, and we will try to get all the PEs", idx)
            start_date = '1980,01,01,00,00,00,000000'
            adj_start_date = '1980,01,01,00,00,00,000000'
        self.update_idx_pe_to_db(
            idx=idx, start_date=start_date, end_date='9999,12,31,00,00,00,000000')
        if idx == 'hsi':
            self.adj_hk_idx_pe(start_date=adj_start_date, end_date=datetime.now().strftime('%Y,%m,%d,%H,%M,%S,%f'))
        else:
            _logger.info('No adjustment needed for index: %s', idx)
        return True
