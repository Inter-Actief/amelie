from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'amelie.api'

    # noinspection PyUnusedImports
    def ready(self):
        # Register all API modules by importing all files where API decorators are used on Django startup.
        # Otherwise, only the API methods in amelie.api.api would be registered by default,
        # and others may appear suddenly when those files are imported somewhere else...
        import amelie.api.api
        import amelie.api.activitystream
        import amelie.api.authentication
        import amelie.api.committee
        import amelie.api.company
        import amelie.api.education
        import amelie.api.narrowcasting
        import amelie.api.news
        import amelie.api.person
        import amelie.api.personal_tab
        import amelie.api.push
        import amelie.api.videos
