"""Ariana log handler.

Originally part of Claudia.

Authors: b.c.peschier, m.kooijman, j.zeilstra & k.alberts
"""

import json
import logging
import socket
import traceback

from django.conf import settings

logger = logging.getLogger(__name__)


class ArianaHandler(logging.Handler):
    """
    Log handler to log messages and exceptions to IRC.

    Communicates to the Ariana IRC bot with Irker.
    """
    _server = None

    def __init__(self, sleep, debug, level=logging.NOTSET):
        """
        Create Ariana log handler.

        :param int sleep: Number of seconds to wait after each IRC message.
        :param bool debug: Use "clau-debug" name instead of "claudia".
        :param int level:
        """
        super(ArianaHandler, self).__init__(level)
        self.sleep = sleep
        self.debug = debug

    def emit(self, record):
        """
        Log a LogRecord to Ariana.

        :param LogRecord record: LogRecord to log to Ariana.
        """
        msg = record.getMessage()

        if record.exc_info:
            # Append exception type and message if there is an exception.
            exctype, value = record.exc_info[:2]
            excmsg = traceback.format_exception_only(exctype, value)[-1].strip()
            msg = '%s - %s' % (msg, excmsg)

        try:
            irc = settings.IRKER_IRC_URL
            chan = settings.IRKER_CLAUDIA_CHANNEL
            key = settings.IRKER_CLAUDIA_CHANNEL_KEY

            if "claudia" in record.name:
                source = "claudia{}".format("-debug" if self.debug else "")
            else:
                source = "{}{}".format(record.name, "-debug" if self.debug else "")

            data = {
                'to': [construct_url(irc, chan, key)],
                'privmsg': "\u0002[{}] \u001F{}\u001F{}\u0002{}".format(source, record.levelname, ": " if record.levelname else "", msg)
            }

            # Send message
            send_package(json.dumps(data))

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def construct_url(irc_server, channel, key):
    return "{}{}{}{}{}".format(irc_server, "" if irc_server[-1] == "/" else "/", channel, "" if key == "" else "?key=", key)


def send_package(package):
    url = settings.IRKER_URL
    port = settings.IRKER_PORT

    # noinspection PyBroadException
    try:
        if url:
            logger.debug("Sending IRC package {} to {}:{}".format(package, url, port))
            #  Connect to Irker server
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.connect((url, port))
            # Send the message
            server.send(package.encode())
            # Close server connection
            server.close()

    except Exception as e:
        try:
            logger.exception('Exception sending IRC message: {}'.format(e))
        except Exception as e2:
            print("Could not log exception {}: {}".format(e, e2))


def send_irc(sender, **kwargs):
    irc = settings.IRKER_IRC_URL
    chan = settings.IRKER_CHANNEL
    key = settings.IRKER_CHANNEL_KEY

    # Check if Irker url and channel are set in the settings. Do not send message if not set.
    if "" not in [irc, chan]:

        from amelie.news.models import NewsItem
        from amelie.activities.models import Activity

        instance = kwargs.get('instance')
        created = kwargs.get("created")

        if sender == NewsItem or sender == Activity:
            msg = ""

            if sender == NewsItem:
                if created:
                    committee = "" if len(instance.publisher.name) == 0 else "[{}]".format(instance.publisher.name)
                    absolute_url = instance.get_absolute_url()
                    title = instance.title
                    introduction = "" if len(instance.introduction) == 0 else " - {}".format(instance.introduction)

                    # Construct message and replace " with ' to avoid problems.
                    msg = "\u0002> \u001Fnews\u001F: {}\u0002 {} - {} <https://www.inter-actief.utwente.nl{}>".format(
                        committee, title, introduction, absolute_url).replace("\"", "'")

            elif sender == Activity:
                if created:
                    date = instance.begin.strftime('%d-%m-%Y')
                    absolute_url = instance.get_absolute_url()
                    title = instance.summary
                    location = "" if len(instance.location) == 0 else " @ {}".format(instance.location)

                    # Construct message and replace " with ' to avoid problems.
                    msg = "\u0002> \u001Fagenda\u001F: [{}]\u0002 {}{} <https://www.inter-actief.utwente.nl{}>".format(date, title, location, absolute_url).replace("\"", "'")

            data = {
                'to': [construct_url(irc, chan, key)],
                'privmsg': msg
            }

            # Send message
            send_package(json.dumps(data))
