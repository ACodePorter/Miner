from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentListField, FloatField, \
    ComplexDateTimeField, StringField


class MarketBreadthSectorScore(EmbeddedDocument):
    sector_key = StringField(required=True)
    score = FloatField(required=True)


class MarketBreadthScore(Document):
    index_name = StringField(required=True)
    trade_date = ComplexDateTimeField(required=True)
    score_sma20 = FloatField(required=True)
    score_sma50 = FloatField(required=True)
    score_sma200 = FloatField(required=True)
    sector_score20 = EmbeddedDocumentListField(MarketBreadthSectorScore)
    sector_score50 = EmbeddedDocumentListField(MarketBreadthSectorScore)
    sector_score200 = EmbeddedDocumentListField(MarketBreadthSectorScore)
