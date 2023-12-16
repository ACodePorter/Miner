import json
from typing import Type

from mongoengine import Document, QuerySet
from pandas import DataFrame

from ._log import get_logger

_logger = get_logger('data_converter')


def df_2_mongo(data: DataFrame, doc: Type[Document]):
    """
    Save DataFrame to MongoDB
    :param data:
    :param doc:
    :return:
    """
    if data is not None and data.shape[0] > 0:
        doc.objects.insert(doc.objects.from_json(
            data.to_json(orient='records')))
    else:
        _logger.warning('Empty DataFrame not saved!')


def mongo_2_df(querySet: QuerySet) -> DataFrame:
    '''
    将数据库中查询到的数据转换为DataFrame,若无数据返回空的DataFrame
    '''
    return DataFrame.from_dict(json.loads(querySet.to_json())).drop('_id', axis=1, errors='ignore')
