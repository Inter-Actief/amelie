# mailnotify.py
# ClaudiaPlugin for notifying users via mail that their account was created/scheduled for deletion.
# authors: b.c.peschier & m.kooijman

import logging

from django.conf import settings

from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.iamailer import MailTask, Recipient


logger = logging.getLogger(__name__)


class MailNotifyPlugin(ClaudiaPlugin):
    def account_created(self, claudia, mp, passwd):
        if not mp.email:
            logger.info("Not sending email, no mail address")
            return

        if mp.is_person():
            self._sendmail('claudia/account_created.mail', mp, {"password": passwd})

    def account_scheduled_delete(self, claudia, mp):
        if not mp.email:
            logger.info("Not sending email, no mail address")
            return

        self._sendmail('claudia/account_deleted.mail', mp)

    @staticmethod
    def _sendmail(template, mp, extra_context=None):
        if not extra_context:
            extra_context = {}

        conf = settings.CLAUDIA_MAIL

        language = None

        task = MailTask(from_=conf["FROM"], template_name=template, report_to=conf["FROM"], report_always=False)

        if 'preferred_language' in mp.extra_data():
            language = mp.extra_data()['preferred_language']

        aliases = ['%s@inter-actief.net' % pa for pa in mp.personal_aliases()]

        context = {
            'name': mp.name,
            'email': aliases[0] if aliases else mp.email,
        }

        if len(aliases) > 1:
            context['alias'] = ', '.join(aliases[1:])

        if mp.adname:
            context['account'] = mp.adname

        for key in extra_context:
            context[key] = extra_context[key]

        task.add_recipient(Recipient(
            tos=['"{}" <{}>'.format(mp.name, mp.email)],
            context=context,
            language=language
            ))

        # Send e-mail
        task.send(delay=False)
