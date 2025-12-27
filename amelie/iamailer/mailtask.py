from typing import List, Dict, Any

from amelie.iamailer.tasks import send_mails


class MailTask:
    def __init__(self, from_: str = None, template_name: str = None, template_string: str = None,
                 report_to: str = None, report_language: str = None, report_always: bool = True, priority: int = 5):
        """
        Create a task to send e-mails.
        :param from_: Sender of the message "Name <email@domain.local>"
        :param template_name: Name of the template to use, or:
        :param template_string: String containing the template to use
        :param report_to: Where to send the delivery report
        :param report_language: In which language to send the delivery report
        :param report_always: True if you always want a delivery report, False if you only want one if some mails fail to send.
        :param priority: Priority with which the mails are sent. Can be a number from 1 (lowest) to 10 (highest).
                         5 is the default. Priority is only used if the mails are sent in the background.
        """
        self.from_: str = from_
        self.template_name: str = template_name
        self.template_string: str = template_string
        self.report_to: str = report_to
        self.report_language: str = report_language
        self.report_always: bool = report_always
        self.priority: int = priority

        self.recipients: List['Recipient'] = []

    def add_recipient(self, recipient: 'Recipient'):
        """
        Add a recipient to the list of recipients.
        :param recipient: The new recipient.
        """
        self.recipients.append(recipient)

    def send(self, delay: bool = True):
        """
        Send the mails as specified.
        :param delay: If True, send the mails in the background, if False, the mails are sent immediately.
        """
        mails: List[Dict[str, Any]] = [recipient.get_maildata() for recipient in self.recipients]

        send_kwargs = {
            "mail_from": self.from_,
            "mails": mails,
            "template_name": self.template_name,
            "template_string": self.template_string,
            "report_to": self.report_to,
            "report_language": self.report_language,
            "report_always": self.report_always
        }

        if delay:
            send_mails.s(**send_kwargs).set(priority=self.priority).delay()
        else:
            send_mails(**send_kwargs)


class Recipient(object):
    def __init__(self, tos, context=None, headers=None, ccs=None, bccs=None, language=None, attachments=None):
        self.tos = tos
        self.context = context if context else {}
        self.headers = headers if headers else {}
        self.ccs = ccs if ccs else []
        self.bccs = bccs if bccs else []
        self.language = language
        self.attachments = attachments

    def get_maildata(self):
        return {
            'to': self.tos,
            'cc': self.ccs,
            'bcc': self.bccs,
            'headers': self.headers,
            'context': self.context,
            'language': self.language,
            'attachments': self.attachments,
        }
