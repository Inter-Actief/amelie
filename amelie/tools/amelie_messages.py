from django.contrib.messages import add_message
from django.utils.safestring import mark_safe


def with_actions(request, level, message, actions, extra_tags='', fail_silently=False,
                 format_str='<a class="action_button" href="{1}">{0}</a>'):
    """Add a message to the queue with actions

    :param actions: A list of tuples with name and url to a certain action
    :param format_str: A string dictating how the action buttons should be rendered
    """

    buttons = " ".join([format_str.format(name, url) for (name, url) in actions])

    final_message = '{0} {1}'.format(message, buttons)

    add_message(request, level, mark_safe(final_message), extra_tags, fail_silently)
