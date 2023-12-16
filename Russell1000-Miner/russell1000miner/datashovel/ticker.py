from mongoengine import Document, StringField


class Ticker(Document):
    ticker = StringField(required=True)
    name = StringField(required=True)
    sector = StringField()
    cusip = StringField()
    isin = StringField()
    sedol = StringField()
    as_of_date = StringField()
