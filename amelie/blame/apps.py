from django.apps import AppConfig


class BlameConfig(AppConfig):
    name = 'amelie.blame'

    def ready(self):
        # Register all AuditLog hooks from the registrations.py file.
        # noinspection PyUnresolvedReferences
        from . import registrations
