import datetime, locale


class unicode_datetime(datetime.datetime):

    def strftime(self, format):
        enc = locale.getpreferredencoding()
        return datetime.datetime.strftime(self, format.encode(enc)).decode(enc)


def unicodify_datetime(dt):
    return unicode_datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                            dt.second, dt.microsecond, dt.tzinfo)
