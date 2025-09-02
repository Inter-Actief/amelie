from amelie.iamailer.tasks import send_mails


class MailTask(object):
    def __init__(self, from_=None, template_name=None, template_string=None, report_to=None, report_language=None,
                 report_always=True):
        self.from_ = from_
        self.template_name = template_name
        self.template_string = template_string
        self.report_to = report_to
        self.report_language = report_language
        self.report_always = report_always

        self.recipients = []

    def add_recipient(self, recipient):
        self.recipients.append(recipient)

    def send(self, delay=True):
        mails = [recipient.get_maildata() for recipient in self.recipients]

        func = send_mails

        if delay:
            func = func.delay

        func(
            mail_from=self.from_,
            mails=mails,
            template_name=self.template_name,
            template_string=self.template_string,
            report_to=self.report_to,
            report_language=self.report_language,
            report_always=self.report_always)


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
