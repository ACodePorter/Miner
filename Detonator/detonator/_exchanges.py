import pytz

IDX_COUNTRY_EXCHANGE_MAP = {
    'hsi': ('hk', 'XHKG', pytz.timezone('Asia/Hong_Kong')),
    '^HSI': ('hk', 'XHKG', pytz.timezone('Asia/Hong_Kong')),
    'spx': ('us', 'XNYS', pytz.timezone('America/New_York')),
    '^SPX': ('us', 'XNYS', pytz.timezone('America/New_York')),
    'qqq': ('us', 'XNYS', pytz.timezone('America/New_York')),
    'ndx': ('us', 'XNYS', pytz.timezone('America/New_York')),
    '^NDX': ('us', 'XNYS', pytz.timezone('America/New_York')),
}
