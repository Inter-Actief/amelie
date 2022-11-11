from celery.task import task

from amelie.iamailer.mailer import send_mails_from_template


# Jelte 2014-04-28: Time limit has been changed to 2 hours because sending the emails
# currently takes about 5 seconds per email (possibly due to a bug).
# Kevin 2020-11-10: Time limit increased to 4 hours (14400 seconds). Sending to 1000 members using the SNT mailserver
# costs 3 seconds per mail, plus 5 seconds delay per mail to avoid overloading.
@task(time_limit=4 * 60 * 60)
def send_mails(mails, from_=None, template_name=None, template_string=None, report_to=None, report_language=None,
               report_always=True):
    """
    See send_mails_from_template from amelie.iamailer.mailer for usage information.
    """
    return send_mails_from_template(mails=mails, from_=from_, template_name=template_name, template_string=template_string,
                                    report_to=report_to, report_language=report_language, report_always=report_always)
