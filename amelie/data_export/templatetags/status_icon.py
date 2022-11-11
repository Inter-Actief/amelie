from django import template
from django.utils.safestring import mark_safe

from amelie.data_export.models import ApplicationStatus

register = template.Library()


@register.filter()
def status_icon(application_status):
    """
    Wrap the given status in a span with an icon appropriate to the given status.
    :type application_status: amelie.data_export.models.ApplicationStatus
    """

    if application_status.status == ApplicationStatus.StatusChoices.NOT_STARTED:
        icon_class = "icon-hourglass"
    elif application_status.status == ApplicationStatus.StatusChoices.RUNNING:
        icon_class = "icon-arrow_rotate_clockwise"
    elif application_status.status == ApplicationStatus.StatusChoices.SUCCESS:
        icon_class = "icon-accept"
    elif application_status.status == ApplicationStatus.StatusChoices.ERROR:
        icon_class = "icon-cancel"
    else:
        icon_class = "icon-help"

    return mark_safe("<div class=\"icon status_icon {}\"></div><span class=\"status_icon_text\">{}</span>".format(
        icon_class, application_status.get_status_display()
    ))
