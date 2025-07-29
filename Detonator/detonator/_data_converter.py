import json
from typing import Type

from mongoengine import Document, NotUniqueError, QuerySet
from pandas import DataFrame

from ._log import get_logger

_logger = get_logger('data_converter')


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
