from typing import Dict

import yfinance as yf
from detonator import SingletonParent, dict_to_mongo, make_db_connection

from .models import Balancesheet, CashflowTable, Financials


class FinancialShovel(SingletonParent):

    def financial_reports_2_db(self, ticker: str, freq: str = 'yearly') -> None:
        """
        获取指定股票的财报三张表,并保存到数据库
        ticker: ticker of stock
        freq: yearly/quarterly
        """
        make_db_connection()
        ticker_ = yf.Ticker(ticker)
        balance: Dict = ticker_.get_balance_sheet(freq=freq, as_dict=True)
        for k, v in balance.items():
            v['ticker'] = ticker
            v['freq'] = freq
            v['end_date'] = k.date()
            dict_to_mongo(v, Balancesheet, ingnore_not_unique_error=True)
        cashflow = ticker_.get_cashflow(freq=freq, as_dict=True)
        for k, v in cashflow.items():
            v['ticker'] = ticker
            v['freq'] = freq
            v['end_date'] = k.date()
            dict_to_mongo(v, CashflowTable, ingnore_not_unique_error=True)

        financials = ticker_.get_financials(freq=freq, as_dict=True)
        for k, v in financials.items():
            v['ticker'] = ticker
            v['freq'] = freq
            v['end_date'] = k.date()
            dict_to_mongo(v, Financials, ingnore_not_unique_error=True)

    def update_financial_reports_yh_2_db(self):
        make_db_connection()
