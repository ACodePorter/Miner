from mongoengine import Document, StringField, ListField, EmbeddedDocument, EmbeddedDocumentField

class Bar(EmbeddedDocument):
    ticker = StringField(required=True)
    interval = StringField(required=True)
    meta = {
        'ordering': ['ticker', 'interval'],
        'index_background': True,
        'auto_create_index': True,
        'auto_create_index_on_save': False,
        'indexes': [
            {
                'fields': ['ticker', 'interval'],
                'unique': True,
            },
            {
                'fields': ['interval', 'ticker'],
                'unique': True,
            }
        ]
    }



class Watchlist(Document):
    user_id = StringField(required=True)
    tickers = ListField(StringField())
    bars = ListField(EmbeddedDocumentField(Bar))
    meta = {
        'ordering': ['user_id'],
        'index_background': True,
        'auto_create_index': True,
        'auto_create_index_on_save': False,
        'indexes': [
            {
                'fields': ['user_id'],
                'unique': True,
            }
        ]
    }


