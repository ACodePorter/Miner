from mongoengine import (ComplexDateTimeField, Document, FloatField, IntField,
                         StringField)


class TickerMinInfo(Document):
    ticker = StringField(required=True)
    timestamp = ComplexDateTimeField(required=True)
    open = FloatField()
    close = FloatField()
    low = FloatField()
    high = FloatField()
    volume = IntField()

    meta = {
        'indexes': [
            {
                'fields': ['ticker', 'timestamp'],
                'unique': True
            }
        ]
    }
