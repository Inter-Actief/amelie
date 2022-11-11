import logging

from django.core.management.base import BaseCommand


def _show_logger(stdout, logger):
    stdout.write('disabled: %s' % ('true' if logger.disabled else 'false'))
    stdout.write('level: %s' % logger.level)
    stdout.write('propagate: %s' % ('true' if logger.propagate else 'false'))
    stdout.write('filters: %s' % logger.filters)
    stdout.write('handlers: %s' % logger.handlers)
    stdout.write('')


class Command(BaseCommand):
    help = "Get the current logging settings"

    def handle(self, *args, **options):
        root_logger = logging.getLogger()

        manager = root_logger.manager

        d = manager.loggerDict

        keys = d.keys()
        keys.sort()

        loggers = {}

        for k in keys:
            logger = d[k]
            if not isinstance(logger, logging.PlaceHolder):
                loggers[k] = logger

        handlers = set([handler for logger in loggers.values() for handler in logger.handlers])

        self.stdout.write('= Handlers =')
        for handler in handlers:
            self.stdout.write('== %s ==' % handler)
            if handler.get_name():
                self.stdout.write('name: %s' % handler.get_name())
            self.stdout.write('level: %s' % handler.level)
            self.stdout.write('filters: %s' % handler.filters)
            self.stdout.write('')

        keys = loggers.keys()
        keys.sort()

        self.stdout.write('= Root logger =')
        _show_logger(self.stdout, root_logger)

        self.stdout.write('= Loggers =')
        for k in keys:
            logger = loggers[k]
            self.stdout.write('== %s ==' % k)
            _show_logger(self.stdout, logger)
