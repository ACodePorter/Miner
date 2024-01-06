from mongoengine import Document, StringField, BooleanField


class TradeCalendar(Document):
    country = StringField(required=True)
    cal_date = StringField(required=True)
    is_open = BooleanField(required=True)
    pretrade_date = StringField(required=True)

    meta = {
        'ordering': ['-cal_date'],
        'index_background': True,
        'auto_create_index': True,
        'auto_create_index_on_save': False,
        'indexes': [
            {'fields': ['cal_date', 'country'],
             'unique': True}
        ]

    }
