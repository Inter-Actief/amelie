from django.db.models import Func, DurationField


class DateTimeDifference(Func):
    def __init__(self, t1, t2, **kwargs):
        kwargs.setdefault('output_field', DurationField())
        super(DateTimeDifference, self).__init__(t1, t2, **kwargs)

    def as_mysql(self, compiler, connection):
        return super(DateTimeDifference, self).as_sql(
            compiler, connection,
            function='TIMESTAMPDIFF',
            template="%(function)s(MICROSECOND, %(expressions)s)"
        )
