from mongoengine import ComplexDateTimeField, Document, FloatField, StringField


class MarketPe(Document):
    '''Market PE Ratio Document Model.
    This model represents the Price-to-Earnings (PE) ratio for a specific market index on a given date.
    It is used to store and retrieve PE ratio data from the database.'''
    idx = StringField(required=True)
    trade_date = ComplexDateTimeField(required=True)
    pe = FloatField(required=True)
    yoy_change = FloatField(default=0.0)
    meta = {
        'ordering': ['trade_date', 'idx'],
        'index_background': True,
        'auto_create_index': True,
        'auto_create_index_on_save': False,
        'indexes': [
            {'fields': ['idx', 'trade_date'], 'unique': True}
        ]
    }
