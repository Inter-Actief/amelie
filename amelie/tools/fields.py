from django.db.models import UUIDField


class Char32UUIDField(UUIDField):
    """
    UUIDField that uses a char(32) field to represent UUIDs, as was the default in Django < 5.0 and Mariadb < 10.7
    See: https://docs.djangoproject.com/en/5.0/releases/5.0/#migrating-existing-uuidfield-on-mariadb-10-7
    """
    def db_type(self, connection):
        return "char(32)"

    def get_db_prep_value(self, value, connection, prepared=False):
        value = super().get_db_prep_value(value, connection, prepared)
        if value is not None:
            value = value.hex
        return value
