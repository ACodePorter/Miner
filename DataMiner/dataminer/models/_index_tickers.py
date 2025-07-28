from mongoengine import Document, ListField, StringField


class IndexTickers(Document):
    index_name = StringField(required=True)
    tickers = ListField(StringField())
    as_of_date = StringField(required=True)
    meta = {
        'indexes': [
            {'fields': ['index_name', 'as_of_date'], 'unique': True}
        ]
    }
