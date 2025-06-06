from typing import Literal, Optional
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from detonator import get_logger, SingletonParent
from pandas import DataFrame

from ._ticker_manager import TickerManager
from ._trade_cal import TradeCalendarShovel

_logger = get_logger('IsharesScraper')

_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
_tm: TickerManager = TickerManager.get_instance()


class IsharesScraper(SingletonParent):
    """
    A class to fetch iwd, iwf, and iwm component tickers from iShares ETF pages.
    """
    IDX_URL_MAP = {
        'iwd': 'https://www.ishares.com/us/products/239708/ishares-russell-1000-value-etf',
        'iwf': 'https://www.ishares.com/us/products/239706/ishares-russell-1000-growth-etf',
        'iwm': 'https://www.ishares.com/us/products/239710/ishares-russell-2000-etf'
    }

    def __init__(self):
        pass

    def _get_ishares_holdings_link(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Requests a given iShares ETF page and extracts the "Detailed Holdings and Analytics"
        link's label and href.

        Args:
            url (str): The URL of the iShares ETF page.

        Returns:
            tuple: A tuple containing (link_label, href_link) if found,
                   otherwise (None, None).
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error requesting the {url}", exc_info=e)
            return None, None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the <a> tag with the specific class and text content
        # We can use a dictionary to specify attributes and their values
        # The `string` argument can be used to match the text content
        link_tag = soup.find(
            'a',
            # class_='icon-xls-export',
            string='Detailed Holdings and Analytics'
        )

        if link_tag:
            link_label = link_tag.get_text(strip=True)
            href_link = link_tag.get('href')

            # iShares often provides relative URLs for these links.
            # We need to construct a full URL if it's relative.
            if href_link and not href_link.startswith(('http://', 'https://')):
                # Assume it's a relative path to the base domain
                base_url = url.split('/us/products/')[0] + '/'
                href_link = urljoin(base_url, href_link)

            return link_label, href_link
        else:
            _logger.warning(
                "Link 'Detailed Holdings and Analytics' not found on the page.")
            return None, None

    def _fetch_tickers_by_idx(self, idx: Literal['iwd', 'iwf', 'iwm']) -> DataFrame:
        """
        get the component tickers of the specified index, and return a DataFrame with columns ['ticker', 'name'].
        """
        if idx not in IsharesScraper.IDX_URL_MAP:
            raise ValueError(f'Invalid index code: {idx}')
        _, href = self._get_ishares_holdings_link(
            IsharesScraper.IDX_URL_MAP[idx])
        if href:
            _logger.info(f'Fetching ticker data from {href}')
            data = pd.read_csv(href, names=['Ticker', 'Name', 'Sector', 'Asset Class', 'Market Value', 'Weight (%)',
                                            'Notional Value', 'Quantity', 'Price', 'Location', 'Exchange', 'Currency',
                                            'FX Rate', 'Market Currency', 'Accrual Date'])  # skiprows=9)
            data = data[(data['Asset Class'] == 'Equity')
                        & (data['Ticker'] != '-')
                        & (data['Exchange'] != 'Non-Nms Quotation Service (Nnqs)')
                        & (data['Exchange'] != 'NO MARKET (E.G. UNLISTED)')]
            data = data.dropna()
            data = data[['Ticker', 'Name']]
            data.sort_values(by=['Ticker'], ascending=True,
                             inplace=True, ignore_index=True)
            data.rename({'Ticker': 'ticker', 'Name': 'name'},
                        axis='columns', inplace=True)
            return data
        else:
            _logger.error(
                f'Failed to fetch tickers for index {idx}, href is not found')
            return DataFrame()

    def fetch_tickers_by_idx(self, index_name: Literal['iwd', 'iwf', 'iwm']) -> DataFrame:
        """
        get the component tickers of the specified index, and return a DataFrame with columns ['ticker', 'name'].
        """
        return self._fetch_tickers_by_idx(index_name)

    def fetch_iwd_tickers(self) -> DataFrame:
        """
        get the component tickers of iwd (iShares Russell 1000 Value ETF), and return a DataFrame with columns ['ticker', 'name'].
        """
        return self._fetch_tickers_by_idx('iwd')

    def fetch_iwf_tickers(self) -> DataFrame:
        """
        get the component tickers of iwf (iShares Russell 1000 Growth ETF), and return a DataFrame with columns ['ticker', 'name'].
        """
        return self._fetch_tickers_by_idx('iwf')

    def fetch_iwm_tickers(self) -> DataFrame:
        """
        get the component tickers of iwm (iShares Russell 2000 ETF), and return a DataFrame with columns ['ticker', 'name'].
        """
        return self._fetch_tickers_by_idx('iwm')
