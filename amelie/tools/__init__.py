from django.apps import AppConfig


class ToolsConfig(AppConfig):
    name = 'amelie.tools'

    def ready(self):
        # Make sure signal handlers are connected
        from tools import cors  # noqa
