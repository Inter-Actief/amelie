# Custom MySQL backend to set the default row format to dynamic to support utf8mb4 encoding
# Source: https://github.com/wikimedia/debmonitor/blob/6219784ec0187a5f4465dd368931bfb8c77e2f50/debmonitor/mysql/base.py

# See also https://bd808.com/blog/2017/04/17/making-django-migrations-that-work-with-mysql-55-and-utf8mb4/
# and https://code.djangoproject.com/ticket/18392

from django.db.backends.mysql import base, schema


class DatabaseSchemaEditor(schema.DatabaseSchemaEditor):
    """Override the default MySQL database schema editor to add ROW_FORMAT=dynamic."""
    sql_create_table = "CREATE TABLE %(table)s (%(definition)s) ROW_FORMAT=DYNAMIC"


class DatabaseWrapper(base.DatabaseWrapper):
    """Override the default MySQL database wrapper to use the custom schema editor class."""
    SchemaEditorClass = DatabaseSchemaEditor
