from email.mime.base import MIMEBase

from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives, SafeMIMEMultipart


class EmailMultiAlternativesRelated(EmailMultiAlternatives):
    """
    A version of EmailMultiAlternatives that makes it easy to send multipart/related
    messages. For example, including images for a HTML message is
    made easier.

    Based on EmailMessage and EmailMultiAlternatives.
    """
    related_subtype = 'related'

    def __init__(self, subject='', body='', from_email=None, to=None, bcc=None,
            connection=None, attachments=None, headers=None, alternatives=None,
            related=None, cc=None):
        """
        Initialize a single email message (which can be sent to multiple
        recipients).

        All strings used to create the message can be unicode strings (or UTF-8
        bytestrings). The SafeMIMEText class will handle any necessary encoding
        conversions.
        """
        super(EmailMultiAlternativesRelated, self).__init__(subject, body, from_email, to, bcc, connection, attachments,
                                                            headers, alternatives, cc)
        self.related = related or []

    def attach_related(self, filename=None, content=None, mimetype=None):
        """
        Attaches a file with the given filename and content. The filename can
        be omitted and the mimetype is guessed, if not provided.

        If the first parameter is a MIMEBase subclass it is inserted directly
        into the resulting message attachments.
        """
        if isinstance(filename, MIMEBase):
            assert content == mimetype == None
            self.related.append(filename)
        else:
            assert content is not None
            self.related.append((filename, content, mimetype))

    def _create_message(self, msg):
        return self._create_attachments(self._create_related(self._create_alternatives(msg)))

    def _create_related(self, msg):
        if self.related:
            encoding = self.encoding or settings.DEFAULT_CHARSET
            body_msg = msg
            msg = SafeMIMEMultipart(_subtype=self.related_subtype, encoding=encoding)
            if self.body:
                msg.attach(body_msg)
            for related in self.related:
                if isinstance(related, MIMEBase):
                    msg.attach(related)
                else:
                    msg.attach(self._create_attachment(*related))
        return msg
