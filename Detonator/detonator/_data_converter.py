from typing import Any
from typing import Type

import pandas as pd
from mongoengine import Document, NotUniqueError, QuerySet
from pandas import DataFrame, DatetimeIndex, PeriodIndex, TimedeltaIndex

import logging

from ._log import get_logger

_logger = get_logger('DataConverter', logging.NOTSET)


def dict_to_mongo(data: dict, doc: Type[Document], ingnore_not_unique_error=False):
    """
    Save dict to MongoDB
    :param data:
    :param doc:
    :return:
    """
    try:
        if data is not None and data:
            # doc.objects.insert(doc.objects.from_json(json.dumps(data)))
            doc(**data).save()
        else:
            _logger.warning('Empty dict not saved!')
    except NotUniqueError:
        if not ingnore_not_unique_error:
            raise


def df_2_mongo(data: DataFrame, doc: Type[Document], ingnore_not_unique_error=False):
    """
    Save DataFrame to MongoDB
    :param data:
    :param doc:
    :return:
    """
    try:
        if data is not None and data.shape[0] > 0:
            doc.objects.insert(doc.objects.from_json(
                data.to_json(orient='records')))
        else:
            _logger.warning('Empty DataFrame not saved!')
    except NotUniqueError:
        if not ingnore_not_unique_error:
            raise


def mongo_2_df(querySet: QuerySet) -> DataFrame:
    '''
    将数据库中查询到的数据转换为DataFrame,若无数据返回空的DataFrame
    '''
    return DataFrame(list(querySet.as_pymongo()))


def _resample_ohlcv_session(bars: DataFrame, rule: Any) -> DataFrame:
    '''
    resample ohlcv, the column must include open/high/low/close/volume/timestamp
    '''
    # Anchor bins at 09:30 for this day
    _logger.debug('%s', rule)
    agg = {
        'ticker':'first',
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
    }

    day_midnight = bars.index[0].normalize()
    # this is us market open time in UTC
    session_start = day_midnight + pd.Timedelta(hours=13, minutes=30)
    return bars.resample(
        rule,  # "65min",
        origin=session_start,
        closed="left",
        label="left",
    ).agg(agg)


def resample_ohlcv(bars: DataFrame, rule) -> DataFrame:
    if bars.empty:
        _logger.warning('Empty DataFrame not saved!')
        return bars

    _logger.debug('%s \n rule: %s', bars.columns, rule)
    # Check if required columns exist
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    
    if type(bars.index) in [DatetimeIndex, PeriodIndex, TimedeltaIndex]:
        if not all(col in bars.columns for col in required_columns):
            _logger.warning('Columns %s not exist in DataFrame!', required_columns)
            return DataFrame()
    else:
        # Check if timestamp column exists and other required columns
        if 'timestamp' not in bars.columns or not all(col in bars.columns for col in required_columns):
            _logger.warning('timestamp and columns %s not exist in DataFrame!', required_columns)
            return DataFrame()
        bars = bars.set_index('timestamp', drop=False)


    bars = (
        bars
        .groupby(bars.index.normalize())
        .apply(_resample_ohlcv_session, rule=rule)
        .droplevel(0)
        .dropna(how="all")
    )
    return bars
