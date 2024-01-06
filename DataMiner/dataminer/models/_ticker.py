from mongoengine import Document, StringField


class Ticker(Document):
    """

    """
    ticker = StringField(required=True)
    name = StringField()
    cusip = StringField()
    isin = StringField()
    sedol = StringField()
    as_of_date = StringField()
    industry = StringField()
    industryKey = StringField()
    industryDisp = StringField()
    sector = StringField()
    sectorKey = StringField()
    sectorDisp = StringField()
