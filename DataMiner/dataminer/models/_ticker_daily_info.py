from typing import Dict, Any

from detonator import subdict, common_in_list, get_logger
from mongoengine import Document, ComplexDateTimeField, StringField, FloatField, LongField


class TickerDailyInfo(Document):
    ticker = StringField(required=True)
    interval = StringField(required=True)
    trade_date = ComplexDateTimeField(required=True)
    open = FloatField(required=True)
    low = FloatField(required=True)
    high = FloatField(required=True)
    close = FloatField(required=True)
    volume = FloatField(required=True)
    dividends = FloatField()
    stock_splits = FloatField()
    sma20 = FloatField()
    sma50 = FloatField()
    sma200 = FloatField()
    governanceEpochDate = LongField()
    compensationAsOfEpochDate = LongField()
    dividendRate = FloatField()
    dividendYield = FloatField()
    exDividendDate = LongField()
    payoutRatio = FloatField()
    fiveYearAvgDividendYield = FloatField()
    beta = FloatField()
    trailingPE = FloatField()
    forwardPE = FloatField()
    marketCap = LongField()
    fiftyTwoWeekLow = FloatField()
    fiftyTwoWeekHigh = FloatField()
    priceToSalesTrailing12Months = FloatField()
    fiftyDayAverage = FloatField()
    twoHundredDayAverage = FloatField()
    trailingAnnualDividendRate = FloatField()
    trailingAnnualDividendYield = FloatField()
    enterpriseValue = LongField()
    profitMargins = FloatField()
    floatShares = FloatField()
    sharesOutstanding = FloatField()
    sharesShort = LongField()
    sharesShortPriorMonth = LongField()
    sharesShortPreviousMonthDate = LongField()
    dateShortInterest = LongField()
    sharesPercentSharesOut = FloatField()
    heldPercentInsiders = FloatField()
    heldPercentInstitutions = FloatField()
    shortRatio = FloatField()
    shortPercentOfFloat = FloatField()
    impliedSharesOutstanding = LongField()
    bookValue = FloatField()
    priceToBook = FloatField()
    lastFiscalYearEnd = LongField()
    nextFiscalYearEnd = LongField()
    mostRecentQuarter = LongField()
    earningsQuarterlyGrowth = FloatField()
    netIncomeToCommon = LongField()
    trailingEps = FloatField()
    forwardEps = FloatField()
    pegRatio = FloatField()
    lastSplitFactor = StringField()
    lastSplitDate = LongField()
    enterpriseToRevenue = FloatField()
    enterpriseToEbitda = FloatField()
    # 52WeekChange
    fiftyTwoWeekChange = FloatField()
    SandP52WeekChange = FloatField()
    lastDividendValue = FloatField()
    lastDividendDate = LongField()
    exchange = StringField()
    quoteType = StringField()
    symbol = StringField()
    underlyingSymbol = StringField()
    shortName = StringField()
    longName = StringField()
    firstTradeDateEpochUtc = LongField()
    timeZoneFullName = StringField()
    timeZoneShortName = StringField()
    gmtOffSetMilliseconds = LongField()
    currentPrice = FloatField()
    targetHighPrice = FloatField()
    targetLowPrice = FloatField()
    targetMeanPrice = FloatField()
    targetMedianPrice = FloatField()
    recommendationMean = FloatField()
    recommendationKey = StringField()
    # numberOfAnalystOpinions = IntegerField()
    totalCash = LongField()
    totalCashPerShare = LongField()
    ebitda = LongField()
    totalDebt = LongField()
    quickRatio = FloatField()
    currentRatio = FloatField()
    totalRevenue = LongField()
    debtToEquity = FloatField()
    revenuePerShare = FloatField()
    returnOnAssets = FloatField()
    returnOnEquity = FloatField()
    grossProfits = LongField()
    freeCashflow = LongField()
    operatingCashflow = LongField()
    earningsGrowth = FloatField()
    revenueGrowth = FloatField()
    grossMargins = FloatField()
    ebitdaMargins = FloatField()
    operatingMargins = FloatField()
    financialCurrency = StringField()
    trailingPegRatio = FloatField()
    meta = {
        'ordering': ['trade_date', 'ticker'],
        'index_background': True,
        'auto_create_index': True,
        'auto_create_index_on_save': False,
        'indexes': [
            {
                'fields': ['ticker', 'trade_date', 'interval'],
            },
            {'fields': ['trade_date']},
            {'fields': ['trade_date', 'ticker']},
            {'fields': ['ticker', 'trade_date']},
            {'fields': ['ticker']}
        ]
    }


_ticker_info_keys = [

    'governanceEpochDate',
    'compensationAsOfEpochDate',
    'dividendRate',
    'dividendYield',
    'exDividendDate',
    'payoutRatio',
    'fiveYearAvgDividendYield',
    'beta',
    'trailingPE',
    'forwardPE',
    'marketCap',
    'fiftyTwoWeekLow',
    'fiftyTwoWeekHigh',
    'priceToSalesTrailing12Months',
    'fiftyDayAverage',
    'twoHundredDayAverage',
    'trailingAnnualDividendRate',
    'trailingAnnualDividendYield',
    'enterpriseValue',
    'profitMargins',
    'floatShares',
    'sharesOutstanding',
    'sharesShort',
    'sharesShortPriorMonth',
    'sharesShortPreviousMonthDate',
    'dateShortInterest',
    'sharesPercentSharesOut',
    'heldPercentInsiders',
    'heldPercentInstitutions',
    'shortRatio',
    'shortPercentOfFloat',
    'impliedSharesOutstanding',
    'bookValue',
    'priceToBook',
    'lastFiscalYearEnd',
    'nextFiscalYearEnd',
    'mostRecentQuarter',
    'earningsQuarterlyGrowth',
    'netIncomeToCommon',
    'trailingEps',
    'forwardEps',
    'pegRatio',
    'lastSplitFactor',
    'lastSplitDate',
    'enterpriseToRevenue',
    'enterpriseToEbitda',
    # 52WeekChange
    'fiftyTwoWeekChange',
    'SandP52WeekChange',
    'lastDividendValue',
    'lastDividendDate',
    'exchange',
    'quoteType',
    'symbol',
    'underlyingSymbol',
    'shortName',
    'longName',
    'firstTradeDateEpochUtc',
    'timeZoneFullName',
    'timeZoneShortName',
    'gmtOffSetMilliseconds',
    'currentPrice',
    'targetHighPrice',
    'targetLowPrice',
    'targetMeanPrice',
    'targetMedianPrice',
    'recommendationMean',
    'recommendationKey',
    # 'numberOfAnalystOpinions',
    'totalCash',
    'totalCashPerShare',
    'ebitda',
    'totalDebt',
    'quickRatio',
    'currentRatio',
    'totalRevenue',
    'debtToEquity',
    'revenuePerShare',
    'returnOnAssets',
    'returnOnEquity',
    'grossProfits',
    'freeCashflow',
    'operatingCashflow',
    'earningsGrowth',
    'revenueGrowth',
    'grossMargins',
    'ebitdaMargins',
    'operatingMargins',
    'financialCurrency',
    'trailingPegRatio'
]

_logger = get_logger('TickerDailyInfo')


def regulate_ticker_daily_info(orig_info: Dict[str, Any]) -> Dict[str, Any]:
    if not '52WeekChange' in orig_info:
        _logger.warning('52WeekChange not found for: %s', orig_info['symbol'])
    orig_info['fiftyTwoWeekChange'] = orig_info['52WeekChange'] if '52WeekChange' in orig_info else 0
    return subdict(common_in_list(_ticker_info_keys, list(orig_info.keys())), orig_info)
