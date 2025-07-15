from mongoengine import ComplexDateTimeField, Document, StringField, BooleanField, DateTimeField


class TradeCalendar(Document):
    exchange = StringField()  # e.g., 'XHKG', 'NYSE', etc.
    country = StringField(required=True)
    cal_date = StringField(required=True)  # 'YYYYmmdd' format
    is_open = BooleanField(required=True)
    open = ComplexDateTimeField()         # session open time (nullable)
    break_start = ComplexDateTimeField()  # session break start (nullable)
    break_end = ComplexDateTimeField()    # session break end (nullable)
    close = ComplexDateTimeField()        # session close time (nullable)
    pretrade_date = StringField()  # previous trade date (optional, for compatibility)

    meta = {
        'ordering': ['-cal_date'],
        'index_background': True,
        'auto_create_index': True,
        'auto_create_index_on_save': False,
        'indexes': [
            {'fields': ['cal_date', 'country', 'exchange'], 'unique': True}
        ]
    }
