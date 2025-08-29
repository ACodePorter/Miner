from dataclasses import fields

from mongoengine import Document, FloatField, StringField, LongField


class Bar(Document):
    ticker = StringField(required=True)
    interval = StringField(required=True)
    timestamp = LongField(required=True)
    open = FloatField(required=True)
    high = FloatField(required=True)
    low = FloatField(required=True)
    close = FloatField(required=True)
    volume = FloatField()
    amount = FloatField()

    meta = {
        'index_background': True,
        'auto_create_index': True,
        'auto_create_index_on_save': False,
        'indexes': [
            {'fields': ['ticker', 'interval', 'timestamp'], 'unique': True},
            {'fields': ['ticker', 'interval']},
        ]
    }
